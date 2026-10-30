import importlib


def test_jarvis_module_imports():
    module = importlib.import_module("JARVIS")
    assert hasattr(module, "main")


def test_parser_identifies_known_simple_commands():
    from JARVIS.commands.registry import resolve_command

    assert resolve_command("open notepad")["intent"] == "OPEN_APPLICATION"
    assert resolve_command("open calculator")["intent"] == "OPEN_APPLICATION"
    assert resolve_command("what time is it")["intent"] == "GET_TIME"
    assert resolve_command("what date is it")["intent"] == "GET_DATE"
    assert resolve_command("what is my IP")["intent"] == "NETWORK_INFO"
    assert resolve_command("open downloads")["intent"] == "OPEN_FOLDER"
    assert resolve_command("lock computer")["intent"] == "LOCK_COMPUTER"


def test_unknown_commands_fail_closed():
    from JARVIS.commands.registry import resolve_command

    result = resolve_command("do something weird")
    assert result["intent"] == "UNKNOWN_COMMAND"
