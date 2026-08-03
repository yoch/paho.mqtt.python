from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("apply_hardening_core.py")
text = path.read_text()


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one marker, found {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)


replace_once(
    '''OnDisconnect = Callable[[BaseException | None], Any]\nOnAuth = Callable[[AuthPacket], Any]\n''',
    '''OnDisconnect = Callable[[BaseException | None], Any]\nOnPublish = Callable[[int | None, BaseException | None], Any]\nOnAuth = Callable[[AuthPacket], Any]\n''',
)

replace_once(
    '''        self._callback_worker_task: asyncio.Task[None] | None = None\\n        self._delivery_timeout = delivery_timeout\\n''',
    '''        self._callback_worker_task: asyncio.Task[None] | None = None\\n        self._effect_flush_task: asyncio.Task[None] | None = None\\n        self._delivery_timeout = delivery_timeout\\n''',
)

replace_once(
    '''        self.on_disconnect: OnDisconnect | None = None\n        self.auth_handler: OnAuth | None = auth_handler\n''',
    '''        self.on_disconnect: OnDisconnect | None = None\n        self.on_publish: OnPublish | None = None\n        self.auth_handler: OnAuth | None = auth_handler\n''',
)

replace_once(
    '''    async def _flush_effects(self, *, nowait: bool = False) -> None:\n''',
    '''    def _schedule_effect_flush(self) -> None:\n        task = self._effect_flush_task\n        if task is not None and not task.done():\n            return\n        task = asyncio.create_task(\n            self._flush_effects(), name="mqttnext-effect-flush"\n        )\n        self._effect_flush_task = task\n        task.add_done_callback(self._effect_flush_done)\n\n    def _effect_flush_done(self, task: asyncio.Task[None]) -> None:\n        if self._effect_flush_task is task:\n            self._effect_flush_task = None\n        try:\n            task.result()\n        except asyncio.CancelledError:\n            return\n        except Exception as exc:\n            asyncio.get_running_loop().call_exception_handler(\n                {\n                    "message": "mqttnext scheduled effect flush failed",\n                    "exception": exc,\n                    "task": task,\n                }\n            )\n\n    async def _flush_effects(self, *, nowait: bool = False) -> None:\n''',
)

replace_once(
    '''        elif kind is EffectKind.PUBLISH_COMPLETE:\n            mid: int = effect.data\n            receipt = self._receipts.pop(mid, None)\n            if receipt is not None and receipt._event is not None:\n                receipt._event.set()\n        elif kind is EffectKind.PUBLISH_FAILED:\n            failure: PublishFailure = effect.data\n            receipt = self._receipts.pop(failure.mid, None)\n            if receipt is not None:\n                receipt._error = failure.reason\n                if receipt._event is not None:\n                    receipt._event.set()\n''',
    '''        elif kind is EffectKind.PUBLISH_COMPLETE:\n            mid: int = effect.data\n            receipt = self._receipts.pop(mid, None)\n            if receipt is not None and receipt._event is not None:\n                receipt._event.set()\n            if self.on_publish is not None:\n                await self._enqueue_callback(self.on_publish, mid, None)\n        elif kind is EffectKind.PUBLISH_FAILED:\n            failure: PublishFailure = effect.data\n            receipt = self._receipts.pop(failure.mid, None)\n            if receipt is not None:\n                receipt._error = failure.reason\n                if receipt._event is not None:\n                    receipt._event.set()\n            if self.on_publish is not None:\n                await self._enqueue_callback(\n                    self.on_publish, failure.mid, failure.reason\n                )\n''',
)

replace_once(
    '''        tasks = [self._reader_task, self._writer_task, self._keepalive_task]\\n''',
    '''        tasks = [\\n            self._reader_task,\\n            self._writer_task,\\n            self._keepalive_task,\\n            self._effect_flush_task,\\n        ]\\n''',
)

replace_once(
    '''        if self._keepalive_task is not current:\\n            self._keepalive_task = None\\n        if not preserve_reconnect and self._reconnect_task is not current:\\n''',
    '''        if self._keepalive_task is not current:\\n            self._keepalive_task = None\\n        if self._effect_flush_task is not current:\\n            self._effect_flush_task = None\\n        if not preserve_reconnect and self._reconnect_task is not current:\\n''',
)

main_marker = '''def main() -> None:\n    patch_async_client()\n    patch_errors()\n    write_memory_store()\n    write_sqlite_store()\n'''
replacement = '''def patch_paho() -> None:\n    path = "src/mqttnext/compat/paho.py"\n    replace_once(\n        path,\n        "        self._async.on_disconnect = self._dispatch_disconnect\\n"\n        "        self._async.on_message = self._dispatch_message\\n",\n        "        self._async.on_disconnect = self._dispatch_disconnect\\n"\n        "        self._async.on_message = self._dispatch_message\\n"\n        "        self._async.on_publish = self._dispatch_publish\\n",\n    )\n    text_path = ROOT / path\n    source = text_path.read_text()\n    count = source.count("self._async._spawn_callback(self._async._flush_effects)")\n    if count != 2:\n        raise RuntimeError(f"unexpected Paho flush callback count: {count}")\n    source = source.replace(\n        "self._async._spawn_callback(self._async._flush_effects)",\n        "self._async._schedule_effect_flush()",\n    )\n    old = ''' + "'''" + '''            info = MQTTMessageInfo(mid=receipt.mid, _receipt=receipt, _loop=self._loop)\n            if self.on_publish is not None and receipt.qos != QoS.AT_MOST_ONCE:\n                self._async._spawn_callback(self._watch_publish, receipt)\n            return info\n''' + "'''" + '''\n    new = ''' + "'''" + '''            info = MQTTMessageInfo(mid=receipt.mid, _receipt=receipt, _loop=self._loop)\n            if receipt.qos == QoS.AT_MOST_ONCE:\n                self._async._spawn_callback(\n                    self._dispatch_publish, receipt.mid, None\n                )\n            return info\n''' + "'''" + '''\n    if source.count(old) != 1:\n        raise RuntimeError("Paho callback publish marker changed")\n    source = source.replace(old, new, 1)\n    old = ''' + "'''" + '''        if self.on_publish is not None and receipt.qos == QoS.AT_MOST_ONCE:\n            self._safe_callback(self.on_publish, self, self._userdata, receipt.mid, 0, None)\n        elif receipt.qos != QoS.AT_MOST_ONCE:\n            asyncio.run_coroutine_threadsafe(self._watch_publish(receipt), self._loop)\n        return info\n\n    async def _watch_publish(self, receipt: PublishReceipt) -> None:\n        try:\n            await receipt.wait()\n        except Exception:\n            if self.on_publish is not None:\n                self._safe_callback(\n                    self.on_publish, self, self._userdata, receipt.mid, 1, None\n                )\n            return\n        if self.on_publish is not None:\n            self._safe_callback(\n                self.on_publish, self, self._userdata, receipt.mid, 0, None\n            )\n\n''' + "'''" + '''\n    new = ''' + "'''" + '''        if receipt.qos == QoS.AT_MOST_ONCE:\n            self._loop.call_soon_threadsafe(\n                self._async._spawn_callback,\n                self._dispatch_publish,\n                receipt.mid,\n                None,\n            )\n        return info\n\n    def _dispatch_publish(\n        self, mid: int | None, error: BaseException | None\n    ) -> None:\n        if self.on_publish is None:\n            return\n        reason_code = 0 if error is None else 1\n        self._safe_callback(\n            self.on_publish,\n            self,\n            self._userdata,\n            mid,\n            reason_code,\n            None,\n        )\n\n''' + "'''" + '''\n    if source.count(old) != 1:\n        raise RuntimeError("Paho watcher marker changed")\n    source = source.replace(old, new, 1)\n    old = ''' + "'''" + '''        except Exception:\n            # A user callback must never kill the network loop.\n            pass\n''' + "'''" + '''\n    new = ''' + "'''" + '''        except Exception as exc:\n            loop = self._loop\n            if loop is not None:\n                context = {\n                    "message": "mqttnext Paho-compatible callback failed",\n                    "exception": exc,\n                    "callback": cb,\n                }\n                if on_loop:\n                    loop.call_exception_handler(context)\n                else:\n                    loop.call_soon_threadsafe(\n                        loop.call_exception_handler, context\n                    )\n''' + "'''" + '''\n    if source.count(old) != 1:\n        raise RuntimeError("Paho safe callback marker changed")\n    text_path.write_text(source.replace(old, new, 1))\n\n\ndef main() -> None:\n    patch_async_client()\n    patch_errors()\n    write_memory_store()\n    write_sqlite_store()\n    patch_paho()\n'''
if text.count(main_marker) != 1:
    raise RuntimeError("core main marker changed")
text = text.replace(main_marker, replacement, 1)
path.write_text(text)
