"""Plan Faz 2.2: every instance names its own config and credentials; no implicit Wordfall/production default."""
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import mutations as m
import server
from conftest import APPS, PROD, TEST_CLIENT, write_config
from test_mutations import CREATE, FakeReader, app, preview_apply


class Reader:
    def __init__(self):
        self.calls = []

    def search(self, query):
        self.calls.append(query)
        return iter(())


def test_without_config_env_everything_is_out_of_scope(monkeypatch):
    monkeypatch.delenv('GOOGLE_ADS_CONFIG')
    with pytest.raises(m.Rejected):
        m.Config.load()
    reader = Reader()
    assert server.App(reader).invoke('get_account_status', {})['error']['code'] == 'OUT_OF_SCOPE'
    assert not reader.calls


def test_test_instance_never_falls_back_to_a_production_config(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    write_config(home / '.config' / 'googleads' / 'wordfall' / 'config.json', writes_enabled=True,
                 max_campaign_daily_budget_micros=1)  # the old implicit default location
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('GOOGLE_ADS_CONFIG', str(tmp_path / 'test-instance' / 'config.test.json'))  # not created yet
    with pytest.raises(m.Rejected):
        m.Config.load()
    reader = Reader()
    assert server.App(reader).invoke('search_gaql', {'query': 'SELECT campaign.id FROM campaign'})['error']['code'] == 'OUT_OF_SCOPE'
    assert not reader.calls


def test_each_instance_loads_only_its_own_config(tmp_path, monkeypatch):
    prod = write_config(tmp_path / 'prod' / 'config.json')
    test = write_config(tmp_path / 'test' / 'config.json', customer_id=TEST_CLIENT, test_only=True)
    monkeypatch.setenv('GOOGLE_ADS_CONFIG', str(test))
    config = m.Config.load()
    assert (config.customer_id, config.test_only) == (TEST_CLIENT, True)
    monkeypatch.setenv('GOOGLE_ADS_CONFIG', str(prod))
    assert m.Config.load().customer_id == PROD


def test_test_and_production_invariant(tmp_path):
    base = {'production_customer_id': PROD, 'apps': dict(APPS)}
    with pytest.raises(m.Rejected):
        m.Config.parse({**base, 'customer_id': PROD, 'test_only': True})      # test instance pointing at production
    with pytest.raises(m.Rejected):
        m.Config.parse({**base, 'customer_id': TEST_CLIENT, 'test_only': False})  # non-production without test_only
    with pytest.raises(m.Rejected):
        m.Config.parse({'customer_id': PROD, 'apps': dict(APPS)})             # production id is mandatory


def test_legacy_alias_with_one_time_warning_and_conflict(tmp_path, monkeypatch, capsys, instance_config):
    monkeypatch.delenv('GOOGLE_ADS_CONFIG')
    monkeypatch.setenv('WORDFALL_ADS_CONFIG', str(instance_config))
    assert m.Config.load().customer_id == PROD
    m.Config.load()
    err = capsys.readouterr().err
    assert err.count('WORDFALL_ADS_CONFIG is deprecated; use GOOGLE_ADS_CONFIG') == 1
    monkeypatch.setenv('GOOGLE_ADS_CONFIG', str(instance_config))
    assert m.Config.load().customer_id == PROD                              # same value: fine
    monkeypatch.setenv('GOOGLE_ADS_CONFIG', str(tmp_path / 'other.json'))
    with pytest.raises(m.Rejected):
        m.Config.load()                                                    # different values: ambiguous


def test_credential_directory_has_no_default(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    (home / '.config' / 'googleads' / 'wordfall').mkdir(parents=True)
    (home / '.config' / 'googleads' / 'wordfall' / 'developer-token.txt').write_text('a' * 22)
    monkeypatch.setenv('HOME', str(home))
    with pytest.raises(server.CredentialError):
        server.AdsReader()._client()                                       # old default dir is never read
    monkeypatch.setenv('WORDFALL_ADS_CREDENTIAL_DIR', str(tmp_path / 'empty'))
    with pytest.raises(server.CredentialError):                           # alias honoured, files missing
        server.AdsReader()._client()


def test_startup_refuses_without_instance_environment(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('GOOGLE_ADS_', 'WORDFALL_ADS_'))}
    result = subprocess.run([sys.executable, 'server.py'], cwd=Path(__file__).parent, env=env, input='',
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 2
    problems = json.loads(result.stderr.strip().splitlines()[-1])['problems']
    assert problems == ['GOOGLE_ADS_CONFIG is not set', 'GOOGLE_ADS_CREDENTIAL_DIR is not set']
    assert server.startup_problems({'GOOGLE_ADS_CONFIG': 'a', 'WORDFALL_ADS_CONFIG': 'b',
                                    'GOOGLE_ADS_CREDENTIAL_DIR': 'c'}) == [
        'GOOGLE_ADS_CONFIG and WORDFALL_ADS_CONFIG are both set to different values']


def test_audit_defaults_next_to_instance_config_and_can_be_overridden(tmp_path, monkeypatch, instance_config):
    assert m.default_audit_path() == instance_config.parent / 'audit.jsonl'
    monkeypatch.setenv('GOOGLE_ADS_AUDIT_PATH', str(tmp_path / 'elsewhere.jsonl'))
    assert m.default_audit_path() == tmp_path / 'elsewhere.jsonl'


def test_unconfigured_app_rejected_before_any_rpc(tmp_path):
    a, r = app(tmp_path)
    for change in ({'app_id': 'com.other.app'}, {'app_store': 'APPLE_APP_STORE'}):
        result = a.invoke('preview_create_app_campaign', {**CREATE, **change})
        assert result['error']['code'] == 'OUT_OF_SCOPE'
    assert not r.calls and not r.requests


def test_only_configured_single_store_app_is_usable(tmp_path):
    only_ios = replace(__import__('test_mutations').CFG, apps={'APPLE_APP_STORE': APPS['APPLE_APP_STORE']})
    a, r = app(tmp_path, only_ios)
    assert a.invoke('preview_create_app_campaign', CREATE)['error']['code'] == 'OUT_OF_SCOPE'


def test_account_mismatch_is_rejected_for_the_test_instance(tmp_path):
    config = replace(__import__('test_mutations').CFG, customer_id=TEST_CLIENT, test_only=True)
    a, r = app(tmp_path, config)
    r.account_id = PROD                                                    # API returns the production account
    assert a.invoke('get_account_status', {})['error']['code'] == 'OUT_OF_SCOPE'  # test_only reads check the account
    assert a.invoke('preview_create_app_campaign', CREATE)['error']['code'] == 'OUT_OF_SCOPE'
    assert not r.requests


def test_example_config_is_valid_and_secret_free():
    data = json.loads((Path(__file__).parent / 'config.example.json').read_text())
    config = m.Config.parse(data)
    assert not config.can_write() and not config.test_only


# --- credentials: the selected instance uses only its own credential directory -----------------------------------

def make_credentials(root, token):
    root.mkdir(parents=True)
    (root / 'developer-token.txt').write_text(token + '\n')
    (root / 'service-account.json').write_text('{"type": "service_account", "fake": true}')
    return root


@pytest.fixture
def credential_dirs(tmp_path):
    return (make_credentials(tmp_path / 'cred-prod', 'prodToken_' + 'a' * 12),
            make_credentials(tmp_path / 'cred-test', 'testToken_' + 'b' * 12))


@pytest.fixture
def captured_clients(monkeypatch):
    calls = []

    def fake_load_from_dict(settings, version=None):
        calls.append({'settings': dict(settings), 'version': version})
        return object()
    monkeypatch.setattr(server.GoogleAdsClient, 'load_from_dict', staticmethod(fake_load_from_dict))
    return calls


def test_new_variable_selects_only_its_credentials(monkeypatch, credential_dirs, captured_clients):
    prod, test = credential_dirs
    for chosen, token in ((prod, 'prodToken_' + 'a' * 12), (test, 'testToken_' + 'b' * 12)):
        monkeypatch.setenv('GOOGLE_ADS_CREDENTIAL_DIR', str(chosen))
        server.AdsReader()._client()
        settings = captured_clients[-1]['settings']
        assert settings['developer_token'] == token
        assert settings['json_key_file_path'] == str(chosen / 'service-account.json')
        assert captured_clients[-1]['version'] == server.API_VERSION
    assert len(captured_clients) == 2


def test_legacy_alias_selects_its_credentials(monkeypatch, credential_dirs, captured_clients, capsys):
    _, test = credential_dirs
    monkeypatch.setenv('WORDFALL_ADS_CREDENTIAL_DIR', str(test))
    server.AdsReader()._client()
    assert captured_clients[0]['settings']['json_key_file_path'] == str(test / 'service-account.json')
    assert 'WORDFALL_ADS_CREDENTIAL_DIR is deprecated' in capsys.readouterr().err


def test_same_value_under_both_names_is_accepted(monkeypatch, credential_dirs, captured_clients):
    prod, _ = credential_dirs
    monkeypatch.setenv('GOOGLE_ADS_CREDENTIAL_DIR', str(prod))
    monkeypatch.setenv('WORDFALL_ADS_CREDENTIAL_DIR', str(prod))
    server.AdsReader()._client()
    assert captured_clients[0]['settings']['json_key_file_path'] == str(prod / 'service-account.json')


def test_conflicting_credential_variables_never_build_a_client(monkeypatch, credential_dirs, captured_clients):
    prod, test = credential_dirs
    monkeypatch.setenv('GOOGLE_ADS_CREDENTIAL_DIR', str(prod))
    monkeypatch.setenv('WORDFALL_ADS_CREDENTIAL_DIR', str(test))
    with pytest.raises(server.CredentialError):
        server.AdsReader()._client()
    assert captured_clients == []


def test_missing_or_invalid_token_never_builds_a_client(monkeypatch, tmp_path, captured_clients):
    bad = make_credentials(tmp_path / 'bad', 'x')  # fails the token format check
    for value in (None, str(tmp_path / 'absent'), str(bad)):
        if value is None:
            monkeypatch.delenv('GOOGLE_ADS_CREDENTIAL_DIR', raising=False)
        else:
            monkeypatch.setenv('GOOGLE_ADS_CREDENTIAL_DIR', value)
        with pytest.raises(server.CredentialError):
            server.AdsReader()._client()
    assert captured_clients == []


def test_login_customer_id_comes_from_the_instance_config(tmp_path, monkeypatch, credential_dirs, captured_clients):
    _, test = credential_dirs
    config = write_config(tmp_path / 'test-mcc' / 'config.json', customer_id=TEST_CLIENT, test_only=True,
                          login_customer_id='3333333333')
    monkeypatch.setenv('GOOGLE_ADS_CONFIG', str(config))
    monkeypatch.setenv('GOOGLE_ADS_CREDENTIAL_DIR', str(test))
    server.AdsReader()._client()
    assert captured_clients[0]['settings']['login_customer_id'] == '3333333333'
    monkeypatch.setenv('GOOGLE_ADS_CONFIG', str(write_config(tmp_path / 'prod2' / 'config.json')))
    server.AdsReader()._client()
    assert 'login_customer_id' not in captured_clients[1]['settings']
