from __future__ import absolute_import, division, print_function

import attr
import pytest

import environ

from environ.exceptions import MissingSecretError
from environ.secrets import _SecretStr, INISecrets, VaultEnvSecrets


class TestSecretStr:
    def test_secret_str_no_repr(self):
        """
        Outside of reprs, _SecretStr behaves normally.
        """
        s = _SecretStr("abc")

        assert "'abc'" == repr(s)

    def test_secret_str_censors(self):
        """
        _SecretStr censors it's __repr__ if its called from another __repr__.
        """
        s = _SecretStr("abc")

        @attr.s
        class C(object):
            s = attr.ib()

        assert "C(s=<SECRET>)" == repr(C(s))


@pytest.fixture
def ini_file(tmpdir):
    f = tmpdir.join("foo.ini")
    f.write("""\
[secrets]
password = foobar
db_password = nested!
[other_secrets]
password = barfoo
[yet_another_section]
secret = qux
""")
    return f


@pytest.fixture
def ini(ini_file):
    return INISecrets.from_path(str(ini_file))


class TestIniSecret(object):
    def test_missing_default_raises(self, ini):
        """
        Missing values without a default raise an MissingSecretError.
        """
        @environ.config
        class C(object):
            pw = ini.secret()

        with pytest.raises(MissingSecretError):
            environ.to_config(C, {})

    def test_default(self, ini):
        """
        Defaults are used iff the key is missing.
        """
        @environ.config
        class C(object):
            password = ini.secret(default="not used")
            secret = ini.secret(default="used!")

        cfg = environ.to_config(C, {})

        assert C("foobar", "used!") == cfg

    def test_name_overwrite(self, ini):
        """
        Passsing a specific key name is respected.
        """
        @environ.config
        class C(object):
            pw = ini.secret(name="password")

        cfg = environ.to_config(C, {})

        assert _SecretStr("foobar") == cfg.pw

    def test_overwrite_sections(self, ini):
        """
        The source section can be overwritten.
        """
        ini.section = "yet_another_section"

        @environ.config
        class C(object):
            password = ini.secret(section="other_secrets")
            secret = ini.secret()

        cfg = environ.to_config(C, {})

        assert _SecretStr("barfoo") == cfg.password

    def test_nested(self, ini):
        """
        Prefix building works.
        """
        @environ.config
        class C(object):
            @environ.config
            class DB(object):
                password = ini.secret()

            db = environ.group(DB)

        cfg = environ.to_config(C, {})

        assert _SecretStr("nested!") == cfg.db.password


@pytest.fixture
def vault():
    return VaultEnvSecrets(vault_prefix="SECRET")


class TestVaultEnvSecrets(object):
    def test_returns_secret_str(self, vault):
        """
        The returned strings are `_SecretStr`.
        """
        @environ.config
        class C(object):
            x = vault.secret()

        cfg = environ.to_config(C, {"SECRET_X": "foo"})

        assert isinstance(cfg.x, _SecretStr)
        assert "foo" == cfg.x

    def test_overwrite_name(self, vault):
        """
        The variable name can be overwritten.
        """
        @environ.config
        class C(object):
            password = vault.secret(name="not_password")

        cfg = environ.to_config(C, {
            "SECRET_PASSWORD": "wrong",
            "not_password": "correct",
        })

        assert "correct" == cfg.password

    def test_missing_raises_missing_secret(self, vault):
        """
        Missing values without a default raise an MissingSecretError.
        """
        @environ.config
        class C(object):
            pw = vault.secret()

        with pytest.raises(MissingSecretError):
            environ.to_config(C, {})
