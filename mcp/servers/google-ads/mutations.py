"""Bounded Google Ads mutations; account, apps and limits come from a local config, never from tool arguments."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import warnings

from PIL import Image, UnidentifiedImageError

import grpc
from google.ads.googleads.errors import GoogleAdsException
from jsonschema import Draft202012Validator
import sys

APP_STORES = ("GOOGLE_APP_STORE", "APPLE_APP_STORE")
APP_ID = {"type": "string", "minLength": 1, "maxLength": 255, "pattern": "^[A-Za-z0-9._-]+$"}
# Environment: new names first; the pre-SUPER_COMPUTER_AI names are accepted as deprecated aliases.
ENV_ALIASES = {"GOOGLE_ADS_CONFIG": "WORDFALL_ADS_CONFIG", "GOOGLE_ADS_CREDENTIAL_DIR": "WORDFALL_ADS_CREDENTIAL_DIR"}
_warned = set()


def env_value(name, environ=None):
    """Value of a configuration variable or None. The deprecated alias is honoured with a one-time stderr warning;
    if both names are set to different values the configuration is ambiguous and rejected."""
    environ = os.environ if environ is None else environ
    new, old = environ.get(name) or None, environ.get(ENV_ALIASES[name]) or None
    if new and old and new != old:
        raise Rejected('OUT_OF_SCOPE')
    if old and not new and name not in _warned:
        _warned.add(name)
        print(json.dumps({"warning": f"{ENV_ALIASES[name]} is deprecated; use {name}"}), file=sys.stderr)
    return new or old


def config_path(environ=None):
    value = env_value("GOOGLE_ADS_CONFIG", environ)
    if not value:
        raise Rejected('OUT_OF_SCOPE')  # no implicit default: an instance must name its own config file
    return Path(value).expanduser()


ID = {"type": "string", "pattern": "^[1-9][0-9]{0,18}$"}
MICROS = {"type": "integer", "minimum": 1, "maximum": 9223372036854775807}
CURRENCY = {"type": "string", "pattern": "^[A-Z]{3}$"}


class Rejected(Exception):
    def __init__(self, code):
        self.code = code


@dataclass(frozen=True)
class Config:
    customer_id: str | None = None
    production_customer_id: str | None = None
    apps: dict | None = None
    login_customer_id: str | None = None
    test_only: bool = False
    writes_enabled: bool = False
    max_campaign_daily_budget_micros: int | None = None
    allow_remove: bool = False

    @classmethod
    def load(cls):
        path = config_path()
        if not path.exists():
            raise Rejected('OUT_OF_SCOPE')  # never fall back to another instance's config
        try:
            return cls.parse(json.loads(path.read_text()))
        except (OSError, ValueError, TypeError):
            raise Rejected('OUT_OF_SCOPE') from None

    @classmethod
    def parse(cls, data):
        schema = {'type': 'object', 'additionalProperties': False,
                  'required': ['customer_id', 'production_customer_id', 'apps'], 'properties': {
            'customer_id': {'type': 'string', 'pattern': '^[0-9]{10}$'},
            'production_customer_id': {'type': 'string', 'pattern': '^[0-9]{10}$'},
            'apps': {'type': 'object', 'minProperties': 1, 'additionalProperties': False,
                     'properties': {store: APP_ID for store in APP_STORES}},
            'login_customer_id': {'anyOf': [{'type': 'null'}, {'type': 'string', 'pattern': '^[0-9]{10}$'}]},
            'test_only': {'type': 'boolean'}, 'writes_enabled': {'type': 'boolean'},
            'max_campaign_daily_budget_micros': {'anyOf': [{'type': 'null'}, MICROS]},
            'allow_remove': {'const': False},
        }}
        if not Draft202012Validator(schema).is_valid(data):
            raise Rejected('OUT_OF_SCOPE')
        config = cls(**data)
        # A test instance must not point at production, and production must not claim to be a test instance.
        if config.test_only == (config.customer_id == config.production_customer_id):
            raise Rejected('OUT_OF_SCOPE')
        return config

    def app_matches(self, store, app_id):
        return bool(store) and bool(app_id) and (self.apps or {}).get(store) == app_id

    def can_write(self):
        return self.writes_enabled and self.max_campaign_daily_budget_micros is not None


def object_schema(properties, required=None):
    return {'type': 'object', 'properties': properties, 'required': list(properties) if required is None else required, 'additionalProperties': False}


BASE_SCHEMAS = {
    'set_budget': object_schema({'campaign_id': ID, 'amount_micros': MICROS, 'currency': CURRENCY}),
    'set_campaign_status': object_schema({'campaign_id': ID, 'status': {'enum': ['PAUSED', 'ENABLED']}}),
    'create_app_campaign': object_schema({
        'name': {'type': 'string', 'minLength': 1, 'maxLength': 128},
        'app_store': {'enum': list(APP_STORES)}, 'app_id': APP_ID,
        'amount_micros': MICROS, 'currency': CURRENCY, 'target_cpa_micros': MICROS,
        'language_ids': {'type': 'array', 'items': ID, 'minItems': 1, 'maxItems': 20, 'uniqueItems': True},
        'location_ids': {'type': 'array', 'items': ID, 'minItems': 1, 'maxItems': 100, 'uniqueItems': True},
        'headlines': {'type': 'array', 'items': {'type': 'string', 'minLength': 1, 'maxLength': 30}, 'minItems': 2, 'maxItems': 5, 'uniqueItems': True},
        'descriptions': {'type': 'array', 'items': {'type': 'string', 'minLength': 1, 'maxLength': 90}, 'minItems': 1, 'maxItems': 5, 'uniqueItems': True},
    }),
}
ASSET_IDS = {'type': 'array', 'items': ID, 'minItems': 1, 'maxItems': 20, 'uniqueItems': True}
NAME = {'type': 'string', 'minLength': 1, 'maxLength': 128}
create_schema = BASE_SCHEMAS['create_app_campaign']
create_schema['properties'].update(image_asset_ids=ASSET_IDS, youtube_asset_ids=ASSET_IDS)
BASE_SCHEMAS.update({
    'upload_image_asset': object_schema({'name': NAME, 'image_path': {'type': 'string', 'minLength': 1, 'maxLength': 4096}}),
    'register_youtube_asset': object_schema({'name': NAME, 'youtube_video_id': {'type': 'string', 'pattern': '^[A-Za-z0-9_-]{11}$'}}),
    'create_app_ad': object_schema({'campaign_id': ID, 'ad_group_id': ID,
        **{k: create_schema['properties'][k] for k in ('headlines', 'descriptions', 'image_asset_ids', 'youtube_asset_ids')}},
        ['campaign_id', 'ad_group_id', 'headlines', 'descriptions']),
    'set_app_ad_status': object_schema({'campaign_id': ID, 'ad_group_id': ID, 'ad_id': ID, 'status': {'enum': ['PAUSED', 'ENABLED']}}),
    'set_campaign_targeting': object_schema({'campaign_id': ID, **{k: create_schema['properties'][k] for k in ('location_ids', 'language_ids')}}),
    'set_target_cpa': object_schema({'campaign_id': ID, 'target_cpa_micros': MICROS, 'currency': CURRENCY}),
})
SCHEMAS, DESCRIPTIONS = {}, {}
for action, schema in BASE_SCHEMAS.items():
    SCHEMAS['preview_' + action] = schema
    SCHEMAS[action] = object_schema({**schema['properties'], 'change_hash': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}}, schema['required'] + ['change_hash'])
    DESCRIPTIONS['preview_' + action] = f'Validate {action} without writing Ads data; returns before/after and change_hash. No authorization or idempotency guarantee.'
    DESCRIPTIONS[action] = f'Apply explicitly requested {action} using a matching preview. No automatic retry. Read back with search_gaql afterward.'
DESCRIPTIONS['create_app_campaign'] += ' New campaigns are PAUSED; install tCPA only.'
DESCRIPTIONS['upload_image_asset'] += ' JPEG/PNG, at most 5,000,000 bytes; uploads without attaching to an ad.'
DESCRIPTIONS['register_youtube_asset'] += ' Existing public/unlisted YouTube video only. Does not upload to YouTube or verify visibility.'
DESCRIPTIONS['create_app_ad'] += ' Adds a PAUSED ad to an existing ad group of a configured app campaign; does not replace other ads.'
DESCRIPTIONS['set_campaign_targeting'] += ' Replaces positive location/language criteria; preserves exclusions and other types.'

ACCOUNT_QUERY = "SELECT customer.id, customer.currency_code, customer.test_account, customer.manager FROM customer LIMIT 1"
CAMPAIGN_FIELDS = """campaign.id, campaign.resource_name, campaign.status,
campaign.advertising_channel_sub_type, campaign.app_campaign_setting.app_id,
campaign.app_campaign_setting.bidding_strategy_goal_type, campaign.bidding_strategy_type,
campaign.bidding_strategy, campaign.target_cpa.target_cpa_micros,
campaign.app_campaign_setting.app_store, campaign.campaign_budget,
campaign_budget.resource_name, campaign_budget.amount_micros, campaign_budget.explicitly_shared"""


def checked_account(reader, config):
    rows = list(reader.search(ACCOUNT_QUERY))
    if len(rows) != 1:
        raise Rejected('OUT_OF_SCOPE')
    account = rows[0].get('customer', {})
    if str(account.get('id')) != config.customer_id or account.get('manager', False):
        raise Rejected('OUT_OF_SCOPE')
    if config.test_only and account.get('test_account') is not True:
        raise Rejected('OUT_OF_SCOPE')
    return account


def checked_campaign(reader, config, campaign_id):
    rows = list(reader.search(f'SELECT {CAMPAIGN_FIELDS} FROM campaign WHERE campaign.id = {campaign_id}'))
    if len(rows) != 1:
        raise Rejected('OUT_OF_SCOPE')
    campaign, budget = rows[0].get('campaign', {}), rows[0].get('campaign_budget', {})
    app = campaign.get('app_campaign_setting', {})
    prefix = f'customers/{config.customer_id}/'
    if (str(campaign.get('id')) != campaign_id
        or campaign.get('resource_name') != prefix + 'campaigns/' + campaign_id
        or campaign.get('advertising_channel_sub_type') != 'APP_CAMPAIGN'
        or not config.app_matches(app.get('app_store'), app.get('app_id'))
        or campaign.get('status') not in ('PAUSED', 'ENABLED')
        or not re.fullmatch(re.escape(prefix) + r'campaignBudgets/[0-9]+', budget.get('resource_name', ''))
        or campaign.get('campaign_budget') != budget.get('resource_name')
        or budget.get('explicitly_shared', False)):
        raise Rejected('OUT_OF_SCOPE')
    # Even unexpected shared references cannot let a budget edit affect another campaign.
    refs = list(reader.search('SELECT campaign.id FROM campaign WHERE campaign.campaign_budget = '
                              + "'" + budget['resource_name'] + "' AND campaign.status != 'REMOVED'"))
    if {str(r['campaign']['id']) for r in refs} != {campaign_id}:
        raise Rejected('OUT_OF_SCOPE')
    return {'campaign': campaign, 'budget': budget}


def image_info(path):
    try:
        file = Path(path).expanduser()
        if not file.is_file():
            raise Rejected('INVALID_ARGUMENT')
        with file.open('rb') as stream:
            data = stream.read(5_000_001)
        if not data or len(data) > 5_000_000:
            raise Rejected('INVALID_ARGUMENT')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as img:
                width, height = img.size
                fmt = img.format
                if fmt not in ('JPEG', 'PNG') or getattr(img, 'is_animated', False):
                    raise Rejected('INVALID_ARGUMENT')
                valid = ((width == height and width >= 200)
                         or (width >= 320 and height >= 400 and width * 5 == height * 4)
                         or (width >= 600 and height >= 314 and abs(width * 100 - height * 191) <= 100))
                if not valid:
                    raise Rejected('INVALID_ARGUMENT')
                img.verify()
            # JPEG verify alone does not decode the pixels; reject truncated streams too.
            with Image.open(BytesIO(data)) as img:
                img.load()
        return data, {'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data), 'width': width, 'height': height, 'format': fmt}
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise Rejected('INVALID_ARGUMENT') from None


def checked_assets(reader, config, args):
    result = []
    for key, kind in [('image_asset_ids', 'IMAGE'), ('youtube_asset_ids', 'YOUTUBE_VIDEO')]:
        ids = args.get(key, [])
        if not ids:
            continue
        rows = list(reader.search('SELECT asset.id, asset.resource_name, asset.type FROM asset WHERE asset.id IN (' + ','.join(ids) + ')'))
        assets = [r.get('asset', {}) for r in rows]
        if len(assets) != len(ids) or {str(a.get('id')) for a in assets} != set(ids):
            raise Rejected('OUT_OF_SCOPE')
        for asset in assets:
            if asset.get('type_') != kind or asset.get('resource_name') != f"customers/{config.customer_id}/assets/{asset['id']}":
                raise Rejected('OUT_OF_SCOPE')
        result.extend(assets)
    return sorted(result, key=lambda a: a['resource_name'])


def checked_ad_group(reader, config, args):
    rows = list(reader.search('SELECT ad_group.id, ad_group.resource_name, ad_group.campaign, ad_group.status FROM ad_group WHERE ad_group.id = ' + args['ad_group_id']))
    if len(rows) != 1:
        raise Rejected('OUT_OF_SCOPE')
    group = rows[0].get('ad_group', {})
    prefix = f'customers/{config.customer_id}/'
    if (str(group.get('id')) != args['ad_group_id'] or group.get('resource_name') != prefix + 'adGroups/' + args['ad_group_id']
        or group.get('campaign') != prefix + 'campaigns/' + args['campaign_id'] or group.get('status') not in ('PAUSED', 'ENABLED')):
        raise Rejected('OUT_OF_SCOPE')
    return group


def checked_ad(reader, config, args):
    rows = list(reader.search('SELECT ad_group_ad.resource_name, ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.type FROM ad_group_ad '
                             + f"WHERE ad_group.id = {args['ad_group_id']} AND ad_group_ad.ad.id = {args['ad_id']}"))
    if len(rows) != 1:
        raise Rejected('OUT_OF_SCOPE')
    ad = rows[0].get('ad_group_ad', {})
    if (ad.get('resource_name') != f"customers/{config.customer_id}/adGroupAds/{args['ad_group_id']}~{args['ad_id']}"
        or str(ad.get('ad', {}).get('id')) != args['ad_id']
        or ad.get('status') not in ('PAUSED', 'ENABLED') or ad.get('ad', {}).get('type_') != 'APP_AD'):
        raise Rejected('OUT_OF_SCOPE')
    return ad


def checked_criteria(reader, config, args):
    rows = list(reader.search('SELECT campaign_criterion.resource_name, campaign_criterion.type, campaign_criterion.negative, '
                             'campaign_criterion.location.geo_target_constant, campaign_criterion.language.language_constant '
                             f"FROM campaign_criterion WHERE campaign.id = {args['campaign_id']} AND campaign_criterion.type IN ('LOCATION', 'LANGUAGE') AND campaign_criterion.status != 'REMOVED'"))
    result = []
    for row in rows:
        criterion = row.get('campaign_criterion', {})
        if not re.fullmatch(f"customers/{config.customer_id}/campaignCriteria/{args['campaign_id']}~[0-9]+", criterion.get('resource_name', '')):
            raise Rejected('OUT_OF_SCOPE')
        kind = criterion.get('type_')
        field, member, collection = ('location', 'geo_target_constant', 'geoTargetConstants') if kind == 'LOCATION' else ('language', 'language_constant', 'languageConstants')
        if kind not in ('LOCATION', 'LANGUAGE') or not re.fullmatch(collection + '/[0-9]+', criterion.get(field, {}).get(member, '')):
            raise Rejected('OUT_OF_SCOPE')
        result.append(criterion)
    return sorted(result, key=lambda c: c['resource_name'])


def fill_app_ad(client, config, ad, args):
    for field in ('headlines', 'descriptions'):
        for text in args[field]:
            asset = client.get_type('AdTextAsset')
            asset.text = text
            getattr(ad.app_ad, field).append(asset)
    for key, field, typename in [('image_asset_ids', 'images', 'AdImageAsset'), ('youtube_asset_ids', 'youtube_videos', 'AdVideoAsset')]:
        for value in args.get(key, []):
            asset = client.get_type(typename)
            asset.asset = f'customers/{config.customer_id}/assets/{value}'
            getattr(ad.app_ad, field).append(asset)


def targeting_diff(before, args):
    remove, add = [], []
    for key, kind, field, member, collection in [
        ('language_ids', 'LANGUAGE', 'language', 'language_constant', 'languageConstants'),
        ('location_ids', 'LOCATION', 'location', 'geo_target_constant', 'geoTargetConstants'),
    ]:
        current = [c for c in before['criteria'] if c['type_'] == kind and not c.get('negative', False)]
        wanted = {collection + '/' + i for i in args[key]}
        existing = {c[field][member] for c in current}
        remove.extend(c['resource_name'] for c in current if c[field][member] not in wanted)
        add.extend((field, member, constant) for constant in sorted(wanted - existing))
    return sorted(remove), add


class RequestId(grpc.UnaryUnaryClientInterceptor):
    def __init__(self):
        self.value = None

    def intercept_unary_unary(self, continuation, details, request):
        call = continuation(details, request)
        for key, value in call.trailing_metadata() or ():
            if key == 'request-id' and isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
                self.value = value
        return call


def operations(client, config, action, args, before):
    """Build actual v25 protobuf operations, with no caller-supplied resource names."""
    def operation():
        return client.get_type('MutateOperation')
    if action == 'set_budget':
        op = operation()
        op.campaign_budget_operation.update.resource_name = before['budget']['resource_name']
        op.campaign_budget_operation.update.amount_micros = args['amount_micros']
        op.campaign_budget_operation.update_mask.paths.append('amount_micros')
        return [op]
    if action == 'set_campaign_status':
        op = operation()
        op.campaign_operation.update.resource_name = before['campaign']['resource_name']
        op.campaign_operation.update.status = args['status']
        op.campaign_operation.update_mask.paths.append('status')
        return [op]
    if action in ('upload_image_asset', 'register_youtube_asset'):
        op = operation()
        asset = op.asset_operation.create
        asset.name = args['name']
        if action == 'upload_image_asset':
            asset.image_asset.data = args['_image_bytes']
        else:
            asset.youtube_video_asset.youtube_video_id = args['youtube_video_id']
        return [op]
    if action == 'create_app_ad':
        op = operation()
        ad = op.ad_group_ad_operation.create
        ad.ad_group, ad.status = before['ad_group']['resource_name'], 'PAUSED'
        fill_app_ad(client, config, ad.ad, args)
        return [op]
    if action == 'set_app_ad_status':
        op = operation()
        op.ad_group_ad_operation.update.resource_name = before['ad']['resource_name']
        op.ad_group_ad_operation.update.status = args['status']
        op.ad_group_ad_operation.update_mask.paths.append('status')
        return [op]
    if action == 'set_target_cpa':
        op = operation()
        op.campaign_operation.update.resource_name = before['campaign']['resource_name']
        op.campaign_operation.update.target_cpa.target_cpa_micros = args['target_cpa_micros']
        op.campaign_operation.update_mask.paths.append('target_cpa.target_cpa_micros')
        return [op]
    if action == 'set_campaign_targeting':
        removed, added = targeting_diff(before, args)
        ops = []
        for resource in removed:
            op = operation()
            op.campaign_criterion_operation.remove = resource
            ops.append(op)
        for field, member, constant in added:
            op = operation()
            criterion = op.campaign_criterion_operation.create
            criterion.campaign = before['campaign']['resource_name']
            setattr(getattr(criterion, field), member, constant)
            ops.append(op)
        return ops
    if action != 'create_app_campaign':
        raise Rejected('INVALID_ARGUMENT')
    prefix = f'customers/{config.customer_id}/'
    budget_name, campaign_name, group_name = prefix + 'campaignBudgets/-1', prefix + 'campaigns/-2', prefix + 'adGroups/-3'
    budget_op, campaign_op, group_op, ad_op = [operation() for _ in range(4)]
    budget = budget_op.campaign_budget_operation.create
    budget.resource_name, budget.name = budget_name, args['name'] + ' budget'
    budget.amount_micros, budget.explicitly_shared, budget.delivery_method = args['amount_micros'], False, 'STANDARD'
    campaign = campaign_op.campaign_operation.create
    campaign.resource_name, campaign.name, campaign.campaign_budget = campaign_name, args['name'], budget_name
    campaign.status = 'PAUSED'
    campaign.advertising_channel_type, campaign.advertising_channel_sub_type = 'MULTI_CHANNEL', 'APP_CAMPAIGN'
    campaign.target_cpa.target_cpa_micros = args['target_cpa_micros']
    campaign.app_campaign_setting.app_id, campaign.app_campaign_setting.app_store = args['app_id'], args['app_store']
    campaign.app_campaign_setting.bidding_strategy_goal_type = 'OPTIMIZE_INSTALLS_TARGET_INSTALL_COST'
    campaign.contains_eu_political_advertising = 'DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING'
    group = group_op.ad_group_operation.create
    group.resource_name, group.campaign, group.name, group.status = group_name, campaign_name, args['name'], 'ENABLED'
    ad = ad_op.ad_group_ad_operation.create
    ad.ad_group, ad.status = group_name, 'ENABLED'
    fill_app_ad(client, config, ad.ad, args)
    criteria = []
    for key, field, resource_field, collection in [
        ('language_ids', 'language', 'language_constant', 'languageConstants'),
        ('location_ids', 'location', 'geo_target_constant', 'geoTargetConstants'),
    ]:
        for value in args[key]:
            op = operation()
            criterion = op.campaign_criterion_operation.create
            criterion.campaign = campaign_name
            setattr(getattr(criterion, field), resource_field, collection + '/' + value)
            criteria.append(op)
    return [budget_op, campaign_op, *criteria, group_op, ad_op]


def mutate(reader, config, action, args, before, validate_only):
    client = reader._client()
    request = client.get_type('MutateGoogleAdsRequest')
    request.customer_id, request.validate_only, request.partial_failure = config.customer_id, validate_only, False
    request.mutate_operations.extend(operations(client, config, action, args, before))
    capture = RequestId()
    service = client.get_service('GoogleAdsService', interceptors=[capture])
    try:
        response = service.mutate(request=request, retry=None, timeout=20)
    except GoogleAdsException:
        raise
    except Exception:
        if not validate_only:
            raise Rejected('AMBIGUOUS_OUTCOME') from None
        raise
    if response.partial_failure_error.code:
        raise Rejected('AMBIGUOUS_OUTCOME' if not validate_only else 'API_ERROR')
    resources = []
    for item in response.mutate_operation_responses:
        pb = type(item).pb(item)
        field = pb.WhichOneof('response')
        if field:
            resources.append(getattr(item, field).resource_name)
    return {'request_id': capture.value, 'resource_names': resources}


def default_audit_path():
    """GOOGLE_ADS_AUDIT_PATH, else audit.jsonl next to this instance's config file."""
    explicit = os.environ.get('GOOGLE_ADS_AUDIT_PATH')
    return Path(explicit).expanduser() if explicit else config_path().parent / 'audit.jsonl'


def execute(reader, config, name, arguments, audit_path=None):
    preview = name.startswith('preview_')
    action = name.removeprefix('preview_')
    args = {k: v for k, v in arguments.items() if k != 'change_hash'}
    if action not in BASE_SCHEMAS:
        raise Rejected('INVALID_ARGUMENT')
    for key in ('language_ids', 'location_ids', 'image_asset_ids', 'youtube_asset_ids'):
        if key in args:
            args[key] = sorted(args[key])
    if not preview and not config.can_write():
        raise Rejected('OUT_OF_SCOPE')
    cap = config.max_campaign_daily_budget_micros
    if cap is None:
        raise Rejected('OUT_OF_SCOPE')
    if action == 'create_app_campaign' and not config.app_matches(args['app_store'], args['app_id']):
        raise Rejected('OUT_OF_SCOPE')  # only the configured apps; rejected before any RPC
    account = checked_account(reader, config)
    currency = account.get('currency_code')
    if not currency or ('currency' in args and args['currency'] != currency):
        raise Rejected('INVALID_ARGUMENT')
    account_actions = ('create_app_campaign', 'upload_image_asset', 'register_youtube_asset')
    before = None if action in account_actions else checked_campaign(reader, config, args['campaign_id'])
    if action == 'create_app_campaign':
        if args['amount_micros'] > cap:
            raise Rejected('OUT_OF_SCOPE')
    elif action == 'set_budget':
        if args['amount_micros'] > cap and args['amount_micros'] >= int(before['budget']['amount_micros']):
            raise Rejected('OUT_OF_SCOPE')
    elif action in ('set_campaign_status', 'set_app_ad_status'):
        if args['status'] == 'ENABLED' and int(before['budget']['amount_micros']) > cap:
            raise Rejected('OUT_OF_SCOPE')
    elif before is not None and int(before['budget']['amount_micros']) > cap:
        raise Rejected('OUT_OF_SCOPE')
    if action in ('create_app_campaign', 'create_app_ad'):
        assets = checked_assets(reader, config, args)
        if assets:
            before = {**(before or {}), 'assets': assets}
    if action in ('create_app_ad', 'set_app_ad_status'):
        before['ad_group'] = checked_ad_group(reader, config, args)
    if action == 'set_app_ad_status':
        before['ad'] = checked_ad(reader, config, args)
    if action == 'set_campaign_targeting':
        before['criteria'] = checked_criteria(reader, config, args)
    if action == 'set_target_cpa':
        campaign = before['campaign']
        if (campaign.get('bidding_strategy_type') != 'TARGET_CPA' or campaign.get('bidding_strategy')
            or campaign.get('app_campaign_setting', {}).get('bidding_strategy_goal_type') != 'OPTIMIZE_INSTALLS_TARGET_INSTALL_COST'
            or int(campaign.get('target_cpa', {}).get('target_cpa_micros', 0)) <= 0):
            raise Rejected('OUT_OF_SCOPE')
    image_meta = None
    if action == 'upload_image_asset':
        args['_image_bytes'], image_meta = image_info(args['image_path'])
    after = {k: v for k, v in args.items() if k not in ('image_path', '_image_bytes')}
    if image_meta:
        after['image'] = image_meta
    if action in ('create_app_campaign', 'create_app_ad'):
        after['status'] = 'PAUSED'
    if action == 'create_app_campaign':
        after['goal'] = 'OPTIMIZE_INSTALLS_TARGET_INSTALL_COST'
    payload = {'action': action, 'config': asdict(config), 'before': before, 'after': after, 'currency': currency}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if not preview and arguments['change_hash'] != digest:
        raise Rejected('STALE_PREVIEW')
    if action == 'set_campaign_targeting' and not any(targeting_diff(before, args)):
        return {'status': 'NO_CHANGE', 'before': before, 'after': after, 'currency': currency,
                'change_hash': digest, 'validation': 'NOT_NEEDED', 'readback_required': False}
    # Opening the local audit sink before RPC prevents writes if no audit sink is available.
    path = Path(audit_path).expanduser() if audit_path else default_audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as audit:
        event = {'at': datetime.now(timezone.utc).isoformat(), 'action': name, 'customer_id': config.customer_id,
                 'before': before, 'after': {k: v for k, v in after.items() if k not in ('name', 'headlines', 'descriptions')}, 'change_hash': digest}
        try:
            result = mutate(reader, config, action, args, before, preview)
        except Exception as exc:
            event['status'] = exc.code if isinstance(exc, Rejected) else 'FAILED'
            event['exception_class'] = type(exc).__name__
            rid = getattr(exc, 'request_id', None)
            event['request_id'] = rid if isinstance(rid, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', rid) else None
            audit.write(json.dumps(event) + '\n')
            audit.flush()
            raise
        event.update(result)
        event['status'] = 'VALIDATED' if preview else 'APPLIED_READBACK_REQUIRED'
        try:
            audit.write(json.dumps(event) + '\n')
            audit.flush()
        except OSError:
            # API success must never look like a safely retryable failure if audit failed afterward.
            return {**result, 'status': event['status'], 'audit_error': True, 'readback_required': not preview}
    if preview:
        return {'before': before, 'after': after, 'currency': currency, 'change_hash': digest,
                'validation': 'VALIDATE_ONLY_PASSED', **result}
    return {'status': 'APPLIED_READBACK_REQUIRED', **result, 'readback_required': True}
