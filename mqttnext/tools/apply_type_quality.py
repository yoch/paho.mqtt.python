from pathlib import Path


ENGINE = Path("mqttnext/src/mqttnext/protocol/engine.py")
WEBSOCKET = Path("mqttnext/src/mqttnext/transport/websocket.py")
CLIENT = Path("mqttnext/src/mqttnext/api/async_client.py")
PYPROJECT = Path("mqttnext/pyproject.toml")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


engine = ENGINE.read_text()
engine = replace_once(
    engine,
    """        if isinstance(topics, str):
            topic_list = (topics,)
        else:
            topic_list = tuple(topics)
""",
    """        topic_list: tuple[str, ...]
        if isinstance(topics, str):
            topic_list = (topics,)
        else:
            topic_list = tuple(topics)
""",
    "unsubscribe tuple annotation",
)
ENGINE.write_text(engine)

websocket = WEBSOCKET.read_text()
websocket = replace_once(
    websocket,
    """        for line in lines[1:]:
            if b":" in line:
                k, _, v = line.partition(b":")
""",
    """        for raw_header in lines[1:]:
            if b":" in raw_header:
                k, _, v = raw_header.partition(b":")
""",
    "WebSocket header variable",
)
WEBSOCKET.write_text(websocket)

client = CLIENT.read_text()
client = replace_once(
    client,
    """        elif kind is EffectKind.SUBACK:
            result = SubscribeResult.from_packet(effect.data)
            fut = self._sub_futs.pop(result.mid, None)
            if fut is not None and not fut.done():
                fut.set_result(result)
        elif kind is EffectKind.UNSUBACK:
            result = UnsubscribeResult.from_packet(effect.data)
            fut = self._unsub_futs.pop(result.mid, None)
            if fut is not None and not fut.done():
                fut.set_result(result)
""",
    """        elif kind is EffectKind.SUBACK:
            sub_result = SubscribeResult.from_packet(effect.data)
            sub_fut = self._sub_futs.pop(sub_result.mid, None)
            if sub_fut is not None and not sub_fut.done():
                sub_fut.set_result(sub_result)
        elif kind is EffectKind.UNSUBACK:
            unsub_result = UnsubscribeResult.from_packet(effect.data)
            unsub_fut = self._unsub_futs.pop(unsub_result.mid, None)
            if unsub_fut is not None and not unsub_fut.done():
                unsub_fut.set_result(unsub_result)
""",
    "typed ack futures",
)
client = replace_once(
    client,
    """    def _fail_non_replayable(self, exc: BaseException) -> None:
        for fut in self._sub_futs.values():
            if not fut.done():
                fut.set_exception(exc)
        self._sub_futs.clear()
        for fut in self._unsub_futs.values():
            if not fut.done():
                fut.set_exception(exc)
        self._unsub_futs.clear()
""",
    """    def _fail_non_replayable(self, exc: BaseException) -> None:
        for sub_fut in self._sub_futs.values():
            if not sub_fut.done():
                sub_fut.set_exception(exc)
        self._sub_futs.clear()
        for unsub_fut in self._unsub_futs.values():
            if not unsub_fut.done():
                unsub_fut.set_exception(exc)
        self._unsub_futs.clear()
""",
    "typed failure futures",
)
CLIENT.write_text(client)

pyproject = PYPROJECT.read_text()
if "[tool.mypy]" not in pyproject:
    pyproject += """

[tool.mypy]
python_version = "3.11"
check_untyped_defs = true
ignore_missing_imports = true
show_error_codes = true
"""
PYPROJECT.write_text(pyproject)
