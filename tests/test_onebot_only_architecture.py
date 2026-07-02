from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parent.parent


def test_project_dependencies_are_onebot_only():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps = pyproject["project"]["dependencies"]
    packages = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "nonebot-adapter-onebot>=2.4" in deps
    assert not any(dep.startswith("nonebot-adapter-qq") for dep in deps)
    assert not any(dep.startswith("mcp") for dep in deps)
    assert "mcp_server*" not in packages


def test_removed_framework_files_are_gone():
    assert not (ROOT / "mcp_server").exists()
    assert not (ROOT / "bot" / "__main__.py").exists()
    assert not (ROOT / "docs" / "openclaw-mcp-integration.md").exists()


def test_rpg_plugin_only_imports_onebot_adapter():
    source = (ROOT / "bot" / "plugins" / "rpg.py").read_text(encoding="utf-8")

    assert "nonebot.adapters.onebot.v11" in source
    assert "nonebot.adapters.qq" not in source
    assert "GroupAtMessageCreateEvent" not in source
    assert "C2CMessageCreateEvent" not in source
    assert "AtMessageCreateEvent" not in source
    assert "group_openid" not in source
    assert "guild_" not in source
