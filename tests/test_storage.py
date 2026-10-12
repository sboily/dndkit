"""The campaign store: files, transactions, legacy saves and configuration."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from gamemaster_mcp.config import ENV_DATA_DIR, resolve_data_dir
from gamemaster_mcp.errors import (
    AlreadyExistsError,
    InvalidChangeError,
    NoActiveCampaignError,
    NotFoundError,
)
from gamemaster_mcp.game import characters
from gamemaster_mcp.storage import CampaignStore
from tests.helpers import FIXTURES, make_character


def test_create_never_replaces_an_existing_campaign(store: CampaignStore) -> None:
    with store.transaction() as campaign:
        characters.create(campaign, make_character("Aria"))
    for name in ("Test Campaign", "test campaign", "Test  Campaign!"):
        with pytest.raises(AlreadyExistsError):
            store.create(name, "again")
    assert store.load("Test Campaign").characters


def test_names_without_letters_are_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidChangeError):
        CampaignStore(tmp_path).create("!!!", "d")


def test_tools_need_an_active_campaign(tmp_path: Path) -> None:
    with pytest.raises(NoActiveCampaignError), CampaignStore(tmp_path).transaction():
        pass


def test_failed_transaction_restores_memory_and_disk(store: CampaignStore) -> None:
    path = store.campaigns_dir / "Test Campaign.json"
    before = path.read_text()
    with pytest.raises(NotFoundError), store.transaction() as campaign:
        characters.create(campaign, make_character("Aria"))
        characters.find(campaign, "Nobody")
    assert store.current is not None and store.current.characters == {}
    assert path.read_text() == before


def test_writes_leave_no_temporary_file(store: CampaignStore) -> None:
    with store.transaction() as campaign:
        campaign.world_notes = "fog"
    assert sorted(p.name for p in store.campaigns_dir.iterdir()) == ["Test Campaign.json"]


def test_most_recent_campaign_reopens_and_corrupt_files_are_skipped(tmp_path: Path) -> None:
    first = CampaignStore(tmp_path)
    first.create("Older", "d")
    first.create("Newer", "d")
    broken = tmp_path / "campaigns" / "Broken.json"
    broken.write_text("{not json")
    os.utime(tmp_path / "campaigns" / "Older.json", (2_000_000_000, 2_000_000_000))
    os.utime(broken, (2_100_000_000, 2_100_000_000))
    reopened = CampaignStore(tmp_path)
    assert reopened.current is not None and reopened.current.name == "Older"
    assert "Broken (unreadable)" in [entry.name for entry in reopened.list_campaigns()]


def test_legacy_save_loads_and_migrates(tmp_path: Path) -> None:
    (tmp_path / "campaigns").mkdir()
    shutil.copy(FIXTURES / "legacy_campaign.json", tmp_path / "campaigns" / "Ghost Coast.json")
    store = CampaignStore(tmp_path)
    campaign = store.load("ghost coast")
    aria = characters.find(campaign, "aria")
    assert set(campaign.characters) == {"PUVYW4Xh"}  # re-keyed by ID
    assert (aria.hit_points_current, aria.spell_slots) == (50, {1: 2})
    order = [(c.name, c.initiative) for c in campaign.game_state.initiative_order]
    assert order == [("Goblin", 12), ("Orc", 15), ("Rat", 0)]  # a ghost with "lots" of HP: gone
    assert campaign.quests["Qx7aLmPt"].name == "Find the lighthouse"
    with store.transaction() as live:  # any change rewrites it in the new format
        characters.update(live, "Aria", {"notes": "migrated"}, {})
    assert characters.find(store.load("Ghost Coast"), "Aria").hit_points_current == 1


def test_setting_files_stay_inside_the_settings_folder(
    store: CampaignStore, tmp_path: Path
) -> None:
    (store.settings_dir / "world.md").write_text("# Faerûn", encoding="utf-8")
    (tmp_path / "secret.md").write_text("secret")
    (store.settings_dir / "link.md").symlink_to(tmp_path / "secret.md")
    assert store.read_setting_file("world.md") == "# Faerûn"
    for name in ("../secret.md", "/etc/hosts", "link.md", "world.json"):
        with pytest.raises(InvalidChangeError):
            store.read_setting_file(name)
    with pytest.raises(NotFoundError, match="world.md"):
        store.read_setting_file("missing.md")


def test_data_dir_comes_from_env_else_user_data_dir(tmp_path: Path) -> None:
    assert resolve_data_dir({ENV_DATA_DIR: str(tmp_path)}) == tmp_path.resolve()
    assert resolve_data_dir({ENV_DATA_DIR: "~/campaigns"}) == Path.home() / "campaigns"
    default = resolve_data_dir({})
    assert default.is_absolute() and default.name == "gamemaster-mcp"
    assert resolve_data_dir({ENV_DATA_DIR: "dnd_data"}) == default  # never against the cwd


def test_importing_the_server_touches_no_disk(tmp_path: Path) -> None:
    code = "import gamemaster_mcp.app, gamemaster_mcp.models; gamemaster_mcp.app.build_server()"
    home = tmp_path / "home"
    env = {k: v for k, v in os.environ.items() if k != ENV_DATA_DIR}
    env |= {"HOME": str(home), "XDG_DATA_HOME": str(home / "data")}  # the default data dir too
    work = tmp_path / "work"
    work.mkdir()
    subprocess.run([sys.executable, "-c", code], cwd=work, env=env, check=True)
    assert list(work.iterdir()) == [] and not home.exists()


def test_bad_files_in_the_campaigns_folder_are_skipped(tmp_path: Path) -> None:
    folder = tmp_path / "campaigns"
    folder.mkdir()
    (folder / "gone.json").symlink_to(tmp_path / "nowhere.json")
    (folder / "deep.json").write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")
    store = CampaignStore(tmp_path)
    assert store.current is None
    assert sorted(e.readable for e in store.list_campaigns()) == [False, False]
    store.create("Le Phare Éteint", "d")
    assert store.load("le phare eteint").name == "Le Phare Éteint"
    with pytest.raises(AlreadyExistsError):
        store.create("LE PHARE ETEINT", "again")


def test_a_setting_file_must_be_utf8_text(store: CampaignStore) -> None:
    (store.settings_dir / "Latin.MD").write_bytes("Forêt".encode("latin-1"))
    (store.settings_dir / "folder.md").mkdir()
    with pytest.raises(InvalidChangeError, match="not UTF-8"):
        store.read_setting_file("Latin.MD")
    with pytest.raises(NotFoundError, match=r"Available: Latin\.MD\.$"):
        store.read_setting_file("missing.md")


def test_two_processes_sharing_a_campaign_keep_each_other_s_changes(tmp_path: Path) -> None:
    first = CampaignStore(tmp_path)
    first.create("Shared", "d")
    second = CampaignStore(tmp_path)  # another client, on the same data dir
    with first.transaction() as campaign:
        characters.create(campaign, make_character("Aria"))
    with second.transaction() as campaign:  # reads Aria first, then adds Borin
        characters.create(campaign, make_character("Borin"))
    with first.reading() as campaign:
        assert sorted(c.name for c in campaign.characters.values()) == ["Aria", "Borin"]
    assert sorted(c.name for c in CampaignStore(tmp_path).load("Shared").characters.values()) == [
        "Aria",
        "Borin",
    ]
    assert (tmp_path / ".lock").exists()


def test_a_campaign_deleted_elsewhere_is_no_longer_active(tmp_path: Path) -> None:
    first = CampaignStore(tmp_path)
    first.create("Gone", "d")
    second = CampaignStore(tmp_path)
    second.delete("Gone", second.request_deletion("Gone")[1])
    with pytest.raises(NoActiveCampaignError), first.transaction():
        pass
    assert not list((tmp_path / "campaigns").glob("*.json"))  # not written back
