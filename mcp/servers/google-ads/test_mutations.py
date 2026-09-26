from dataclasses import replace
import json
import re
from types import SimpleNamespace
from copy import deepcopy
from PIL import Image
import pytest
import server
import mutations as m
from conftest import APPS, PROD

CID = PROD
CFG = m.Config(customer_id=PROD, production_customer_id=PROD, apps=dict(APPS),
               writes_enabled=True, max_campaign_daily_budget_micros=500_000_000)
CREATE = dict(name='Example test', app_store='GOOGLE_APP_STORE', app_id=APPS['GOOGLE_APP_STORE'],
              amount_micros=100_000_000, currency='TRY', target_cpa_micros=10_000_000,
              language_ids=['1037'], location_ids=['2792'], headlines=['Example', 'Discover New Words'], descriptions=['Play Example'])


class FakeReader:
    def __init__(self, config=CFG):
        self.config, self.calls, self.requests = config, [], []
        self.budget, self.status, self.app_id, self.store = 200_000_000, 'PAUSED', APPS['GOOGLE_APP_STORE'], 'GOOGLE_APP_STORE'
        self.account_id, self.test_account = config.customer_id, config.test_only
        self.extra_reference, self.failure = False, None
        self.cpa, self.strategy, self.goal = 10_000_000, 'TARGET_CPA', 'OPTIMIZE_INSTALLS_TARGET_INSTALL_COST'
        prefix = f'customers/{config.customer_id}/'
        self.group = {'id': '50', 'resource_name': prefix+'adGroups/50', 'campaign': prefix+'campaigns/42', 'status': 'ENABLED'}
        self.ad = {'resource_name': prefix+'adGroupAds/50~60', 'status': 'ENABLED', 'ad': {'id': '60', 'type_': 'APP_AD'}}
        self.assets = {'71': {'id':'71', 'resource_name':prefix+'assets/71', 'type_':'IMAGE'},
                       '72': {'id':'72', 'resource_name':prefix+'assets/72', 'type_':'YOUTUBE_VIDEO'}}
        self.criteria = [
            {'resource_name':prefix+'campaignCriteria/42~1', 'type_':'LOCATION', 'location':{'geo_target_constant':'geoTargetConstants/2792'}},
            {'resource_name':prefix+'campaignCriteria/42~2', 'type_':'LANGUAGE', 'language':{'language_constant':'languageConstants/1037'}},
            {'resource_name':prefix+'campaignCriteria/42~3', 'type_':'LOCATION', 'negative':True, 'location':{'geo_target_constant':'geoTargetConstants/2840'}},
        ]
        self.created_ads = []
        self.sdk = server.GoogleAdsClient(developer_token='fake', credentials=None, version='v25', use_proto_plus=True)

    def search(self, query):
        self.calls.append(query)
        if 'FROM customer' in query:
            return iter([{'customer': {'id': self.account_id, 'currency_code': 'TRY', 'test_account': self.test_account, 'manager': False}}])
        if 'FROM asset' in query:
            ids = re.search(r'asset.id IN \(([^)]+)\)', query)
            wanted = ids.group(1).split(',') if ids else self.assets
            return iter([{'asset':deepcopy(self.assets[i])} for i in wanted if i in self.assets])
        if 'FROM ad_group_ad' in query:
            return iter([{'ad_group_ad':deepcopy(self.ad)}])
        if 'FROM ad_group ' in query:
            return iter([{'ad_group':deepcopy(self.group)}])
        if 'FROM campaign_criterion' in query:
            return iter([{'campaign_criterion':deepcopy(c)} for c in self.criteria])
        if "campaign.campaign_budget = '" in query:
            return iter([{'campaign': {'id': i}} for i in (['42','43'] if self.extra_reference else ['42'])])
        return iter([{'campaign': {'id': '42', 'resource_name': f'customers/{self.config.customer_id}/campaigns/42',
                     'status': self.status, 'advertising_channel_sub_type': 'APP_CAMPAIGN',
                     'bidding_strategy_type':self.strategy, 'target_cpa':{'target_cpa_micros':str(self.cpa)},
                     'app_campaign_setting': {'app_id': self.app_id, 'app_store': self.store, 'bidding_strategy_goal_type':self.goal},
                     'campaign_budget': f'customers/{self.config.customer_id}/campaignBudgets/10'},
                     'campaign_budget': {'resource_name': f'customers/{self.config.customer_id}/campaignBudgets/10',
                                        'amount_micros': str(self.budget), 'explicitly_shared': False}}])

    def _client(self):
        def get_service(name, interceptors):
            assert name == 'GoogleAdsService'
            def mutate(request, retry, timeout):
                assert retry is None and timeout == 20
                assert request.customer_id == self.config.customer_id
                assert request.partial_failure is False
                self.requests.append(request)
                if self.failure:
                    raise self.failure
                interceptors[0].value = 'request_ABC-123'
                response = self.sdk.get_type('MutateGoogleAdsResponse')
                if not request.validate_only:
                    for op in request.mutate_operations:
                        pb = type(op).pb(op)
                        field = pb.WhichOneof('operation')
                        specific = getattr(op, field)
                        kind = type(specific).pb(specific).WhichOneof('operation')
                        obj = getattr(specific, kind)
                        if field == 'campaign_budget_operation' and kind == 'update': self.budget = obj.amount_micros
                        if field == 'campaign_operation' and kind == 'update':
                            if 'status' in specific.update_mask.paths: self.status = obj.status.name
                            if 'target_cpa.target_cpa_micros' in specific.update_mask.paths: self.cpa = obj.target_cpa.target_cpa_micros
                        if field == 'asset_operation' and kind == 'create':
                            aid = str(100 + len(self.assets))
                            asset_kind = 'IMAGE' if obj.image_asset.data else 'YOUTUBE_VIDEO'
                            self.assets[aid] = {'id':aid, 'resource_name':f'customers/{self.config.customer_id}/assets/{aid}', 'type_':asset_kind,
                                                'name':obj.name, 'youtube_video_asset':{'youtube_video_id':obj.youtube_video_asset.youtube_video_id}}
                            obj.resource_name = self.assets[aid]['resource_name']
                        if field == 'ad_group_ad_operation':
                            if kind == 'update': self.ad['status'] = obj.status.name
                            else:
                                self.created_ads.append(deepcopy(obj))
                                obj.resource_name = f'customers/{self.config.customer_id}/adGroupAds/50~100'
                        if field == 'campaign_criterion_operation':
                            if kind == 'remove': self.criteria = [c for c in self.criteria if c['resource_name'] != obj]
                            elif obj.campaign.endswith('/42'):
                                from google.protobuf.json_format import MessageToDict
                                row = MessageToDict(type(obj).pb(obj), preserving_proto_field_name=True)
                                row['type_'] = 'LOCATION' if 'location' in row else 'LANGUAGE'
                                row['resource_name'] = f'customers/{self.config.customer_id}/campaignCriteria/42~{100+len(self.criteria)}'
                                self.criteria.append(row)
                        result = self.sdk.get_type('MutateOperationResponse')
                        target = getattr(result, field.removesuffix('_operation') + '_result')
                        target.resource_name = obj.resource_name.replace('/-', '/100') if hasattr(obj, 'resource_name') else 'resource'
                        response.mutate_operation_responses.append(result)
                return response
            return SimpleNamespace(mutate=mutate)
        return SimpleNamespace(get_type=self.sdk.get_type, get_service=get_service)


def app(tmp_path, config=CFG):
    reader = FakeReader(config)
    return server.App(reader, lambda: config, tmp_path/'audit.jsonl'), reader


def preview_apply(app, action, args):
    preview = app.invoke('preview_' + action, args)
    assert 'error' not in preview, preview
    return app.invoke(action, {**args, 'change_hash': preview['change_hash']})


def test_budget_status_validate_apply_readback(tmp_path):
    a, r = app(tmp_path)
    result = preview_apply(a, 'set_budget', dict(campaign_id='42', amount_micros=300_000_000, currency='TRY'))
    assert result['status'] == 'APPLIED_READBACK_REQUIRED'
    assert r.budget == 300_000_000
    assert result['request_id'] == 'request_ABC-123'
    assert [x.validate_only for x in r.requests] == [True, False]
    assert list(r.requests[1].mutate_operations[0].campaign_budget_operation.update_mask.paths) == ['amount_micros']
    result = preview_apply(a, 'set_campaign_status', dict(campaign_id='42', status='ENABLED'))
    assert 'error' not in result and r.status == 'ENABLED'
    assert list(r.requests[-1].mutate_operations[0].campaign_operation.update_mask.paths) == ['status']
    events = [json.loads(x) for x in (tmp_path/'audit.jsonl').read_text().splitlines()]
    assert len(events) == 4 and [x['status'] for x in events] == ['VALIDATED','APPLIED_READBACK_REQUIRED'] * 2


def test_create_atomic_paused_real_proto(tmp_path):
    a, r = app(tmp_path)
    result = preview_apply(a, 'create_app_campaign', CREATE)
    assert 'error' not in result, result
    ops = r.requests[-1].mutate_operations
    assert len(ops) == 6
    assert ops[0].campaign_budget_operation.create.explicitly_shared is False
    campaign = ops[1].campaign_operation.create
    assert campaign.status.name == 'PAUSED' and campaign.resource_name.endswith('/-2')
    assert campaign.campaign_budget.endswith('/-1')
    assert campaign.app_campaign_setting.app_id == CREATE['app_id']
    assert campaign.target_cpa.target_cpa_micros == CREATE['target_cpa_micros']
    assert campaign.contains_eu_political_advertising.name == 'DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING'
    assert ops[2].campaign_criterion_operation.create.language.language_constant == 'languageConstants/1037'
    assert ops[3].campaign_criterion_operation.create.location.geo_target_constant == 'geoTargetConstants/2792'
    assert ops[4].ad_group_operation.create.campaign.endswith('/-2')
    assert ops[5].ad_group_ad_operation.create.ad_group.endswith('/-3')
    assert ops[5].ad_group_ad_operation.create.ad.app_ad.headlines[0].text == 'Example'
    assert 'Play Example' not in (tmp_path/'audit.jsonl').read_text()


@pytest.mark.parametrize('change', [
    {'customer_id': '9999999999'}, {'app_id': 'wrong.app'},
    {'app_store': 'APPLE_APP_STORE'}, {'amount_micros': 501_000_000},
    {'currency': 'USD'}, {'amount_micros': True}, {'unknown': 'x'},
])
def test_create_rejected_before_mutation(tmp_path, change):
    a, r = app(tmp_path)
    assert 'error' in a.invoke('preview_create_app_campaign', {**CREATE, **change})
    assert not r.requests


@pytest.mark.parametrize('config', [replace(CFG, writes_enabled=False), replace(CFG, max_campaign_daily_budget_micros=None)])
def test_write_disabled(tmp_path, config):
    a, r = app(tmp_path, config)
    result = a.invoke('create_app_campaign', {**CREATE, 'change_hash': 'a'*64})
    assert result['error']['code'] == 'OUT_OF_SCOPE'
    assert not r.requests and not r.calls


@pytest.mark.parametrize('change', ['budget', 'status', 'config', 'target', 'amount'])
def test_stale_preview(tmp_path, change):
    a, r = app(tmp_path)
    args = dict(campaign_id='42', amount_micros=300_000_000, currency='TRY')
    digest = a.invoke('preview_set_budget', args)['change_hash']
    if change == 'budget': r.budget += 1
    if change == 'status': r.status = 'ENABLED'
    if change == 'config': a.config_loader = lambda: replace(CFG, max_campaign_daily_budget_micros=400_000_000)
    if change == 'target': args['campaign_id'] = '43'
    if change == 'amount': args['amount_micros'] += 1
    result = a.invoke('set_budget', {**args, 'change_hash': digest})
    assert result['error']['code'] in ('STALE_PREVIEW', 'OUT_OF_SCOPE')
    assert len(r.requests) == 1


@pytest.mark.parametrize('case', ['wrong_app','wrong_account','shared_reference'])
def test_scope_rejection(tmp_path, case):
    a, r = app(tmp_path)
    if case == 'wrong_app': r.app_id = 'some.other.app'
    if case == 'wrong_account': r.account_id = '9999999999'
    if case == 'shared_reference': r.extra_reference = True
    result = a.invoke('preview_set_campaign_status', dict(campaign_id='42', status='ENABLED'))
    assert result['error']['code'] == 'OUT_OF_SCOPE' and not r.requests


def test_over_cap_decrease_pause_allowed_enable_denied(tmp_path):
    a, r = app(tmp_path)
    r.budget = 700_000_000
    assert 'error' not in preview_apply(a, 'set_budget', dict(campaign_id='42',amount_micros=600_000_000,currency='TRY'))
    assert 'error' not in preview_apply(a, 'set_campaign_status', dict(campaign_id='42',status='PAUSED'))
    assert 'error' in a.invoke('preview_set_campaign_status', dict(campaign_id='42',status='ENABLED'))
    assert 'error' in a.invoke('preview_set_budget', dict(campaign_id='42',amount_micros=700_000_000,currency='TRY'))


@pytest.mark.parametrize('exc', [TimeoutError('secret-sentinel'), server.google_errors.ServiceUnavailable('secret-sentinel'), RuntimeError('secret-sentinel')])
def test_ambiguous_once_no_retry(tmp_path, exc):
    a, r = app(tmp_path)
    digest = a.invoke('preview_create_app_campaign', CREATE)['change_hash']
    r.failure = exc
    result = a.invoke('create_app_campaign', {**CREATE,'change_hash':digest})
    assert result['error']['code'] == 'AMBIGUOUS_OUTCOME'
    assert len(r.requests) == 2
    assert 'secret-sentinel' not in json.dumps(result) + (tmp_path/'audit.jsonl').read_text()


def test_test_only_guard_all_reads_and_writes(tmp_path):
    base = dict(production_customer_id=CID, apps=dict(APPS))
    for data in [dict(base, customer_id=CID, test_only=True), dict(base, customer_id='1234567890', test_only=False)]:
        with pytest.raises(m.Rejected): m.Config.parse(data)
    config = replace(CFG, customer_id='1234567890', test_only=True)
    a, r = app(tmp_path, config)
    r.test_account = False
    assert a.invoke('search_gaql', {'query':'SELECT campaign.id FROM campaign'})['error']['code'] == 'OUT_OF_SCOPE'
    assert len(r.calls) == 1 and 'FROM customer' in r.calls[0]
    assert 'error' in a.invoke('preview_create_app_campaign', CREATE)
    assert not r.requests
    r.test_account = True
    assert 'error' not in preview_apply(a, 'create_app_campaign', CREATE)


def test_config_invalid_denied_without_rpc(tmp_path):
    a, r = app(tmp_path)
    a.config_loader = lambda: replace(CFG, customer_id='9876543210')
    assert a.invoke('get_account_status', {})['error']['code'] == 'OUT_OF_SCOPE'
    assert not r.calls


def test_request_id_interceptor():
    capture = m.RequestId()
    call = SimpleNamespace(trailing_metadata=lambda: [('request-id','safe_123')])
    assert capture.intercept_unary_unary(lambda *_: call, None, None) is call
    assert capture.value == 'safe_123'


def test_config_file_strict_and_reload(tmp_path, monkeypatch):
    path = tmp_path/'config.json'
    monkeypatch.setenv('GOOGLE_ADS_CONFIG', str(path))
    with pytest.raises(m.Rejected): m.Config.load()
    base = {'customer_id': CID, 'production_customer_id': CID, 'apps': dict(APPS)}
    for data in [{**base, 'writes_enabled': 'true'}, {**base, 'allow_remove': True},
                 {**base, 'max_campaign_daily_budget_micros': True}, {**base, 'unknown': 1},
                 {'writes_enabled': False}, {**base, 'apps': {}}, {**base, 'apps': {'OTHER_STORE': 'x'}}]:
        path.write_text(json.dumps(data))
        with pytest.raises(m.Rejected): m.Config.load()
    path.write_text(json.dumps({**base, 'writes_enabled': False}))
    assert not m.Config.load().can_write()
    path.write_text(json.dumps({**base, 'writes_enabled': True, 'max_campaign_daily_budget_micros': 10}))
    assert m.Config.load().can_write()


def test_audit_open_failure_prevents_rpc(tmp_path):
    a, r = app(tmp_path)
    a.audit_path = tmp_path  # Existing directory cannot be opened as an append file.
    result = a.invoke('preview_create_app_campaign', CREATE)
    assert result['error']['code'] == 'API_ERROR' and not r.requests


def test_apple_create_store_pair(tmp_path):
    a, r = app(tmp_path)
    result = preview_apply(a, 'create_app_campaign', {**CREATE, 'app_store': 'APPLE_APP_STORE', 'app_id': APPS['APPLE_APP_STORE']})
    assert 'error' not in result
    setting = r.requests[-1].mutate_operations[1].campaign_operation.create.app_campaign_setting
    assert setting.app_store.name == 'APPLE_APP_STORE' and setting.app_id == APPS['APPLE_APP_STORE']


def test_audit_failure_after_success_preserves_applied_outcome(tmp_path, monkeypatch):
    a, r = app(tmp_path)
    args = dict(campaign_id='42', amount_micros=300_000_000, currency='TRY')
    digest = a.invoke('preview_set_budget', args)['change_hash']
    class FailingSink:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def write(self, *args): raise OSError('secret-sentinel')
    monkeypatch.setattr(m.Path, 'open', lambda *args, **kwargs: FailingSink())
    result = a.invoke('set_budget', {**args, 'change_hash': digest})
    assert result['status'] == 'APPLIED_READBACK_REQUIRED' and result['audit_error'] is True
    assert result['request_id'] == 'request_ABC-123' and result['readback_required'] is True
    assert r.budget == 300_000_000 and len(r.requests) == 2
    assert 'secret-sentinel' not in json.dumps(result)


def test_create_requires_two_headlines_before_rpc(tmp_path):
    a, r = app(tmp_path)
    result = a.invoke('preview_create_app_campaign', {**CREATE, 'headlines': ['Example']})
    assert result['error']['code'] == 'INVALID_ARGUMENT'
    assert not r.calls and not r.requests


@pytest.mark.parametrize('field,code', [('mutate_error', 'API_ERROR'), ('authorization_error', 'AUTH_ERROR')])
def test_definitive_google_apply_rejection(tmp_path, field, code, capsys):
    import grpc
    from google.ads.googleads.v25.errors.types.errors import GoogleAdsFailure, GoogleAdsError
    a, r = app(tmp_path)
    digest = a.invoke('preview_create_app_campaign', CREATE)['change_hash']
    failure = GoogleAdsFailure()
    item = GoogleAdsError(message='secret-sentinel')
    setattr(item.error_code, field, 1)
    failure.errors.append(item)
    r.failure = server.GoogleAdsException(grpc.RpcError(), None, failure, 'apply_rejected-123')
    result = a.invoke('create_app_campaign', {**CREATE, 'change_hash': digest})
    assert result['error']['code'] == code
    assert result['error']['request_id'] == 'apply_rejected-123'
    assert len(r.requests) == 2
    assert [request.validate_only for request in r.requests] == [True, False]
    audit_text = (tmp_path/'audit.jsonl').read_text()
    events = [json.loads(line) for line in audit_text.splitlines()]
    assert len(events) == 2
    assert events[-1]['status'] == 'FAILED'
    assert events[-1]['exception_class'] == 'GoogleAdsException'
    assert events[-1]['request_id'] == 'apply_rejected-123'
    output = capsys.readouterr()
    assert not output.out
    assert 'secret-sentinel' not in json.dumps(result) + audit_text + output.err


AD_CREATE = dict(campaign_id='42', ad_group_id='50', headlines=['Example', 'Play Example'],
                 descriptions=['A word game'], image_asset_ids=['71'], youtube_asset_ids=['72'])


def test_text_only_app_ad_preview_apply(tmp_path):
    a, r = app(tmp_path)
    args = {k:v for k,v in AD_CREATE.items() if k not in ('image_asset_ids','youtube_asset_ids')}
    for name in ('preview_create_app_ad','create_app_ad'):
        assert 'image_asset_ids' not in server.SCHEMAS[name]['required']
        assert 'youtube_asset_ids' not in server.SCHEMAS[name]['required']
        assert server.SCHEMAS[name]['additionalProperties'] is False
    result = preview_apply(a,'create_app_ad',args)
    assert result['status'] == 'APPLIED_READBACK_REQUIRED'
    ad = r.created_ads[-1]
    assert ad.status.name == 'PAUSED'
    assert len(ad.ad.app_ad.headlines) == 2 and len(ad.ad.app_ad.descriptions) == 1
    assert not ad.ad.app_ad.images and not ad.ad.app_ad.youtube_videos
    assert [q.validate_only for q in r.requests] == [True,False]
    assert not any('FROM asset' in q for q in r.calls)


@pytest.mark.parametrize('action', ['create_app_ad', 'create_app_campaign'])
@pytest.mark.parametrize('field', ['image_asset_ids', 'youtube_asset_ids'])
@pytest.mark.parametrize('preview', [True, False])
def test_empty_optional_media_rejected_before_api(tmp_path, action, field, preview):
    a, r = app(tmp_path)
    args = {**(AD_CREATE if action == 'create_app_ad' else CREATE), field: []}
    if not preview:
        args['change_hash'] = '0' * 64
    result = a.invoke(('preview_' if preview else '') + action, args)
    assert result['error']['code'] == 'INVALID_ARGUMENT'
    assert not r.calls and not r.requests


def test_asset_optional_schema_and_atomic_campaign_media(tmp_path):
    a, r = app(tmp_path)
    for name in ('create_app_campaign', 'preview_create_app_campaign'):
        assert 'image_asset_ids' not in server.SCHEMAS[name]['required']
        assert 'youtube_asset_ids' not in server.SCHEMAS[name]['required']
        assert server.SCHEMAS[name]['additionalProperties'] is False
    assert 'error' not in preview_apply(a, 'create_app_campaign', CREATE)
    result = preview_apply(a, 'create_app_campaign', {**CREATE, 'image_asset_ids':['71'], 'youtube_asset_ids':['72']})
    assert 'error' not in result
    ad = r.requests[-1].mutate_operations[-1].ad_group_ad_operation.create.ad.app_ad
    assert ad.images[0].asset == f'customers/{CID}/assets/71'
    assert ad.youtube_videos[0].asset == f'customers/{CID}/assets/72'


@pytest.mark.parametrize('fmt,size', [('PNG',(200,200)),('JPEG',(600,314)),('PNG',(320,400))])
def test_image_upload_preview_unchanged_apply_readback(tmp_path, fmt, size):
    a, r = app(tmp_path)
    path = tmp_path/'arbitrary-extension.dat'
    Image.new('RGB',size,'red').save(path,format=fmt)
    args = {'name':'private-asset-name', 'image_path':str(path)}
    p = a.invoke('preview_upload_image_asset',args)
    assert 'error' not in p, p
    assert len(r.assets) == 2 and not r.created_ads
    assert p['after']['image']['width'] == size[0]
    assert str(path) not in json.dumps(p)
    r.budget += 1  # Account asset upload is independent of campaign before-state.
    out = a.invoke('upload_image_asset',{**args,'change_hash':p['change_hash']})
    assert out['status'] == 'APPLIED_READBACK_REQUIRED'
    read = a.invoke('search_gaql',{'query':'SELECT asset.id, asset.type FROM asset'})
    assert len(read['rows']) == 3 and not r.created_ads
    assert r.requests[-1].mutate_operations[0].asset_operation.create.image_asset.data == path.read_bytes()
    audit = (tmp_path/'audit.jsonl').read_text()
    assert 'private-asset-name' not in audit and str(path) not in audit
    assert [q.validate_only for q in r.requests] == [True,False]


def test_image_changed_same_path_is_stale(tmp_path):
    a, r = app(tmp_path)
    path = tmp_path/'image.png'
    Image.new('RGB',(200,200),'red').save(path)
    args = {'name':'image', 'image_path':str(path)}
    p = a.invoke('preview_upload_image_asset',args)
    Image.new('RGB',(200,200),'blue').save(path)
    result = a.invoke('upload_image_asset',{**args,'change_hash':p['change_hash']})
    assert result['error']['code'] == 'STALE_PREVIEW' and len(r.requests) == 1


@pytest.mark.parametrize('case', ['too_small','wrong_ratio','gif','corrupt','too_large','directory','missing','truncated_jpeg'])
def test_invalid_image_has_no_mutation(tmp_path, case):
    a, r = app(tmp_path)
    path = tmp_path/'image.png'
    if case == 'directory': path = tmp_path
    elif case == 'missing': pass
    elif case == 'too_large': path.write_bytes(b'x'*5_000_001)
    elif case == 'corrupt': path.write_bytes(b'not a png')
    else:
        size = (199,199) if case == 'too_small' else ((300,200) if case == 'wrong_ratio' else (200,200))
        Image.new('RGB',size).save(path,format='GIF' if case == 'gif' else ('JPEG' if case == 'truncated_jpeg' else 'PNG'))
        if case == 'truncated_jpeg': path.write_bytes(path.read_bytes()[:-40])
    result = a.invoke('preview_upload_image_asset',{'name':'image','image_path':str(path)})
    assert result['error']['code'] == 'INVALID_ARGUMENT' and not r.requests


def test_youtube_register_account_only_and_readback(tmp_path):
    a, r = app(tmp_path)
    args = {'name':'Example clip','youtube_video_id':'AbCdEfGh123'}
    p = a.invoke('preview_register_youtube_asset',args)
    assert 'error' not in p and len(r.assets) == 2
    assert all('FROM customer' in q for q in r.calls)
    result = a.invoke('register_youtube_asset',{**args,'change_hash':p['change_hash']})
    assert 'error' not in result
    rows = a.invoke('search_gaql',{'query':'SELECT asset.id, asset.youtube_video_asset.youtube_video_id FROM asset'})['rows']
    assert rows[-1]['asset']['youtube_video_asset']['youtube_video_id'] == args['youtube_video_id']
    assert not r.created_ads


def test_paused_ad_create_and_separate_status_readback(tmp_path):
    a, r = app(tmp_path)
    old_ad = deepcopy(r.ad)
    p = a.invoke('preview_create_app_ad',AD_CREATE)
    assert 'error' not in p and not r.created_ads and r.ad == old_ad
    result = a.invoke('create_app_ad',{**AD_CREATE,'change_hash':p['change_hash']})
    assert 'error' not in result
    ad = r.created_ads[-1]
    assert ad.status.name == 'PAUSED' and ad.ad_group == r.group['resource_name']
    assert ad.ad.app_ad.images[0].asset.endswith('/71') and ad.ad.app_ad.youtube_videos[0].asset.endswith('/72')
    assert r.ad == old_ad
    result = preview_apply(a, 'set_app_ad_status',dict(campaign_id='42',ad_group_id='50',ad_id='60',status='PAUSED'))
    assert 'error' not in result
    row = a.invoke('search_gaql',{'query':'SELECT ad_group_ad.status FROM ad_group_ad'})['rows'][0]
    assert row['ad_group_ad']['status'] == 'PAUSED'
    assert list(r.requests[-1].mutate_operations[0].ad_group_ad_operation.update_mask.paths) == ['status']


@pytest.mark.parametrize('change', ['asset_type','asset_account','missing_asset','group_campaign','group_status','ad_resource','ad_type'])
def test_management_scope_rejection(tmp_path, change):
    a, r = app(tmp_path)
    args, action = AD_CREATE, 'create_app_ad'
    if change == 'asset_type': r.assets['71']['type_'] = 'YOUTUBE_VIDEO'
    if change == 'asset_account': r.assets['71']['resource_name'] = 'customers/9999999999/assets/71'
    if change == 'missing_asset': del r.assets['71']
    if change == 'group_campaign': r.group['campaign'] = f'customers/{CID}/campaigns/43'
    if change == 'group_status': r.group['status'] = 'REMOVED'
    if change in ('ad_resource','ad_type'):
        args, action = dict(campaign_id='42',ad_group_id='50',ad_id='60',status='PAUSED'), 'set_app_ad_status'
        if change == 'ad_resource': r.ad['resource_name'] = f'customers/{CID}/adGroupAds/51~60'
        else: r.ad['ad']['type_'] = 'RESPONSIVE_SEARCH_AD'
    result = a.invoke('preview_'+action,args)
    assert result['error']['code'] == 'OUT_OF_SCOPE' and not r.requests


def test_targeting_atomic_diff_preserves_exclusions_and_noop(tmp_path):
    a, r = app(tmp_path)
    args = dict(campaign_id='42',location_ids=['2826'],language_ids=['1037','1000'])
    before = deepcopy(r.criteria)
    p = a.invoke('preview_set_campaign_targeting',args)
    assert 'error' not in p and r.criteria == before
    result = a.invoke('set_campaign_targeting',{**args,'change_hash':p['change_hash']})
    assert 'error' not in result
    assert len(r.requests[-1].mutate_operations) == 3
    assert r.requests[-1].partial_failure is False
    rows = a.invoke('search_gaql',{'query':'SELECT campaign_criterion.resource_name FROM campaign_criterion'})['rows']
    assert len(rows) == 4
    assert before[2] in r.criteria and before[1] in r.criteria and before[0] not in r.criteria
    count = len(r.requests)
    no_change = a.invoke('preview_set_campaign_targeting',{**args,'language_ids':['1000','1037']})
    assert no_change['status'] == 'NO_CHANGE' and no_change['validation'] == 'NOT_NEEDED'
    assert len(r.requests) == count


def test_target_cpa_changes_no_budget_or_status(tmp_path):
    a, r = app(tmp_path)
    args = dict(campaign_id='42',target_cpa_micros=12_000_000,currency='TRY')
    p = a.invoke('preview_set_target_cpa',args)
    assert 'error' not in p and r.cpa == 10_000_000
    old = (r.budget,r.status)
    result = a.invoke('set_target_cpa',{**args,'change_hash':p['change_hash']})
    assert 'error' not in result and (r.budget,r.status) == old
    row = a.invoke('search_gaql',{'query':'SELECT campaign.target_cpa.target_cpa_micros FROM campaign'})['rows'][0]
    assert row['campaign']['target_cpa']['target_cpa_micros'] == '12000000'
    assert list(r.requests[-1].mutate_operations[0].campaign_operation.update_mask.paths) == ['target_cpa.target_cpa_micros']


@pytest.mark.parametrize('field,value', [('strategy','TARGET_ROAS'),('goal','OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CONVERSION_COST'),('cpa',0)])
def test_cpa_rejects_other_bidding(tmp_path,field,value):
    a, r = app(tmp_path)
    setattr(r,field,value)
    result = a.invoke('preview_set_target_cpa',dict(campaign_id='42',target_cpa_micros=12,currency='TRY'))
    assert result['error']['code'] == 'OUT_OF_SCOPE' and not r.requests


@pytest.mark.parametrize('action,args,change', [
    ('create_app_ad',AD_CREATE,'group'),
    ('set_campaign_targeting',dict(campaign_id='42',location_ids=['2826'],language_ids=['1037']),'criteria'),
    ('set_target_cpa',dict(campaign_id='42',target_cpa_micros=12,currency='TRY'),'cpa'),
])
def test_management_stale_state(tmp_path,action,args,change):
    a, r = app(tmp_path)
    p = a.invoke('preview_'+action,args)
    assert 'error' not in p
    if change == 'group': r.group['status'] = 'PAUSED'
    elif change == 'criteria': r.criteria.pop()
    else: r.cpa += 1
    result = a.invoke(action,{**args,'change_hash':p['change_hash']})
    assert result['error']['code'] == 'STALE_PREVIEW' and len(r.requests) == 1


@pytest.mark.parametrize('action,args', [
    ('upload_image_asset',dict(name='image',image_path='/nonexistent')),
    ('register_youtube_asset',dict(name='video',youtube_video_id='AbCdEfGh123')),
    ('create_app_ad',AD_CREATE),
    ('set_app_ad_status',dict(campaign_id='42',ad_group_id='50',ad_id='60',status='ENABLED')),
    ('set_campaign_targeting',dict(campaign_id='42',location_ids=['2826'],language_ids=['1037'])),
    ('set_target_cpa',dict(campaign_id='42',target_cpa_micros=12,currency='TRY')),
])
def test_new_actions_config_barrier(tmp_path,action,args):
    for config in (replace(CFG,writes_enabled=False),replace(CFG,max_campaign_daily_budget_micros=None)):
        a, r = app(tmp_path,config)
        result = a.invoke(action,{**args,'change_hash':'a'*64})
        assert result['error']['code'] == 'OUT_OF_SCOPE' and not r.requests and not r.calls


@pytest.mark.parametrize('action,args', [
    ('create_app_ad',AD_CREATE),
    ('set_app_ad_status',dict(campaign_id='42',ad_group_id='50',ad_id='60',status='ENABLED')),
    ('set_campaign_targeting',dict(campaign_id='42',location_ids=['2826'],language_ids=['1037'])),
    ('set_target_cpa',dict(campaign_id='42',target_cpa_micros=12,currency='TRY')),
])
def test_new_campaign_effects_cap(tmp_path,action,args):
    a, r = app(tmp_path)
    r.budget = 600_000_000
    assert a.invoke('preview_'+action,args)['error']['code'] == 'OUT_OF_SCOPE'
    assert not r.requests


def test_new_actions_ambiguous_no_retry_and_audit_redacted(tmp_path):
    a, r = app(tmp_path)
    p = a.invoke('preview_create_app_ad',AD_CREATE)
    r.failure = TimeoutError('secret-sentinel')
    result = a.invoke('create_app_ad',{**AD_CREATE,'change_hash':p['change_hash']})
    assert result['error']['code'] == 'AMBIGUOUS_OUTCOME' and len(r.requests) == 2
    log = (tmp_path/'audit.jsonl').read_text()
    assert 'A word game' not in log and 'Play Example' not in log and 'secret-sentinel' not in log


def test_real_v25_json_type_fields_feed_scope_checks(tmp_path):
    from google.protobuf.json_format import MessageToDict
    a, r = app(tmp_path)
    for name, kind in [('Asset','IMAGE'),('Ad','APP_AD'),('CampaignCriterion','LOCATION')]:
        obj = r.sdk.get_type(name)
        obj.type_ = kind
        data = MessageToDict(type(obj).pb(obj),preserving_proto_field_name=True)
        assert data == {'type_':kind}
    asset = r.sdk.get_type('Asset')
    asset.id, asset.resource_name, asset.type_ = 71, f'customers/{CID}/assets/71', 'IMAGE'
    r.assets['71'] = MessageToDict(type(asset).pb(asset),preserving_proto_field_name=True)
    assert m.checked_assets(r,CFG,{'image_asset_ids':['71']})[0]['type_'] == 'IMAGE'
    assert m.checked_ad(r,CFG,dict(ad_group_id='50',ad_id='60'))['ad']['type_'] == 'APP_AD'
