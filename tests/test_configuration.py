import pytest

from pyhgtmap.configuration import NestedConfig


@pytest.fixture()
def config() -> NestedConfig:
    return NestedConfig()


class TestNestedConfig:
    @staticmethod
    def test_nested_config_setattr(config: NestedConfig) -> None:
        config.attr1 = "value1"
        config.attr2 = "value2"

        assert config.attr1 == "value1"
        assert config.attr2 == "value2"

    @staticmethod
    def test_nested_config_missing_subconfig(config: NestedConfig) -> None:
        with pytest.raises(
            AttributeError, match="'NestedConfig' object has no attribute 'sub_attr'"
        ):
            config.sub_attr.attr = "value1"

    @staticmethod
    def test_nested_config_setattr_missing_subconfig(config: NestedConfig) -> None:
        with pytest.raises(
            AttributeError, match="'NestedConfig' object has no attribute 'sub_attr'"
        ):
            setattr(config, "sub_attr.attr", "value1")

    @staticmethod
    def test_nested_config_add_sub_config(config: NestedConfig) -> None:
        sub_config = NestedConfig()
        sub_config.attr1 = "value1"
        sub_config.attr2 = "value2"

        config.add_sub_config("sub_config", sub_config)

        assert config.sub_config.attr1 == "value1"
        assert config.sub_config.attr2 == "value2"
