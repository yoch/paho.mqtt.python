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


async_ops = r'''
    replace_once(
        path,
        "OnDisconnect = Callable[[BaseException | None], Any]\n"
        "OnAuth = Callable[[AuthPacket], Any]\n",
        "OnDisconnect = Callable[[BaseException | None], Any]\n"
        "OnPublish = Callable[[int | None, BaseException | None], Any]\n"
        "OnAuth = Callable[[AuthPacket], Any]\n",
    )

    replace_once(
        path,
        "        self._callback_worker_task: asyncio.Task[None] | None = None\n"
        "        self._delivery_timeout = delivery_timeout\n",
        "        self._callback_worker_task: asyncio.Task[None] | None = None\n"
        "        self._effect_flush_task: asyncio.Task[None] | None = None\n"
        "        self._delivery_timeout = delivery_timeout\n",
    )

    replace_once(
        path,
        "        self.on_disconnect: OnDisconnect | None = None\n"
        "        self.auth_handler: OnAuth | None = auth_handler\n",
        "        self.on_disconnect: OnDisconnect | None = None\n"
        "        self.on_publish: OnPublish | None = None\n"
        "        self.auth_handler: OnAuth | None = auth_handler\n",
    )

    replace_once(
        path,
        "    async def _flush_effects(self, *, nowait: bool = False) -> None:\n",
        "    def _schedule_effect_flush(self) -> None:\n"
        "        task = self._effect_flush_task\n"
        "        if task is not None and not task.done():\n"
        "            return\n"
        "        task = asyncio.create_task(\n"
        "            self._flush_effects(), name=\"mqttnext-effect-flush\"\n"
        "        )\n"
        "        self._effect_flush_task = task\n"
        "        task.add_done_callback(self._effect_flush_done)\n\n"
        "    def _effect_flush_done(self, task: asyncio.Task[None]) -> None:\n"
        "        if self._effect_flush_task is task:\n"
        "            self._effect_flush_task = None\n"
        "        try:\n"
        "            task.result()\n"
        "        except asyncio.CancelledError:\n"
        "            return\n"
        "        except Exception as exc:\n"
        "            asyncio.get_running_loop().call_exception_handler(\n"
        "                {\n"
        "                    \"message\": \"mqttnext scheduled effect flush failed\",\n"
        "                    \"exception\": exc,\n"
        "                    \"task\": task,\n"
        "                }\n"
        "            )\n\n"
        "    async def _flush_effects(self, *, nowait: bool = False) -> None:\n",
    )

    replace_once(
        path,
        "        elif kind is EffectKind.PUBLISH_COMPLETE:\n"
        "            mid: int = effect.data\n"
        "            receipt = self._receipts.pop(mid, None)\n"
        "            if receipt is not None and receipt._event is not None:\n"
        "                receipt._event.set()\n"
        "        elif kind is EffectKind.PUBLISH_FAILED:\n"
        "            failure: PublishFailure = effect.data\n"
        "            receipt = self._receipts.pop(failure.mid, None)\n"
        "            if receipt is not None:\n"
        "                receipt._error = failure.reason\n"
        "                if receipt._event is not None:\n"
        "                    receipt._event.set()\n",
        "        elif kind is EffectKind.PUBLISH_COMPLETE:\n"
        "            mid: int = effect.data\n"
        "            receipt = self._receipts.pop(mid, None)\n"
        "            if receipt is not None and receipt._event is not None:\n"
        "                receipt._event.set()\n"
        "            if self.on_publish is not None:\n"
        "                await self._enqueue_callback(self.on_publish, mid, None)\n"
        "        elif kind is EffectKind.PUBLISH_FAILED:\n"
        "            failure: PublishFailure = effect.data\n"
        "            receipt = self._receipts.pop(failure.mid, None)\n"
        "            if receipt is not None:\n"
        "                receipt._error = failure.reason\n"
        "                if receipt._event is not None:\n"
        "                    receipt._event.set()\n"
        "            if self.on_publish is not None:\n"
        "                await self._enqueue_callback(\n"
        "                    self.on_publish, failure.mid, failure.reason\n"
        "                )\n",
    )

    replace_once(
        path,
        "        tasks = [self._reader_task, self._writer_task, self._keepalive_task]\n",
        "        tasks = [\n"
        "            self._reader_task,\n"
        "            self._writer_task,\n"
        "            self._keepalive_task,\n"
        "            self._effect_flush_task,\n"
        "        ]\n",
    )

    replace_once(
        path,
        "        if self._keepalive_task is not current:\n"
        "            self._keepalive_task = None\n"
        "        if not preserve_reconnect and self._reconnect_task is not current:\n",
        "        if self._keepalive_task is not current:\n"
        "            self._keepalive_task = None\n"
        "        if self._effect_flush_task is not current:\n"
        "            self._effect_flush_task = None\n"
        "        if not preserve_reconnect and self._reconnect_task is not current:\n",
    )
'''
replace_once("\n\ndef patch_errors() -> None:\n", async_ops + "\n\ndef patch_errors() -> None:\n")

patch_paho_source = r'''

def patch_paho() -> None:
    path = "src/mqttnext/compat/paho.py"
    replace_once(
        path,
        "        self._async.on_disconnect = self._dispatch_disconnect\n"
        "        self._async.on_message = self._dispatch_message\n",
        "        self._async.on_disconnect = self._dispatch_disconnect\n"
        "        self._async.on_message = self._dispatch_message\n"
        "        self._async.on_publish = self._dispatch_publish\n",
    )
    text_path = ROOT / path
    source = text_path.read_text()
    count = source.count("self._async._spawn_callback(self._async._flush_effects)")
    if count != 2:
        raise RuntimeError(f"unexpected Paho flush callback count: {count}")
    source = source.replace(
        "self._async._spawn_callback(self._async._flush_effects)",
        "self._async._schedule_effect_flush()",
    )
    old = ''' + "'''" + r'''            info = MQTTMessageInfo(mid=receipt.mid, _receipt=receipt, _loop=self._loop)
            if self.on_publish is not None and receipt.qos != QoS.AT_MOST_ONCE:
                self._async._spawn_callback(self._watch_publish, receipt)
            return info
''' + "'''" + r'''
    new = ''' + "'''" + r'''            info = MQTTMessageInfo(mid=receipt.mid, _receipt=receipt, _loop=self._loop)
            if receipt.qos == QoS.AT_MOST_ONCE:
                self._async._spawn_callback(
                    self._dispatch_publish, receipt.mid, None
                )
            return info
''' + "'''" + r'''
    if source.count(old) != 1:
        raise RuntimeError("Paho callback publish marker changed")
    source = source.replace(old, new, 1)
    old = ''' + "'''" + r'''        if self.on_publish is not None and receipt.qos == QoS.AT_MOST_ONCE:
            self._safe_callback(self.on_publish, self, self._userdata, receipt.mid, 0, None)
        elif receipt.qos != QoS.AT_MOST_ONCE:
            asyncio.run_coroutine_threadsafe(self._watch_publish(receipt), self._loop)
        return info

    async def _watch_publish(self, receipt: PublishReceipt) -> None:
        try:
            await receipt.wait()
        except Exception:
            if self.on_publish is not None:
                self._safe_callback(
                    self.on_publish, self, self._userdata, receipt.mid, 1, None
                )
            return
        if self.on_publish is not None:
            self._safe_callback(
                self.on_publish, self, self._userdata, receipt.mid, 0, None
            )

''' + "'''" + r'''
    new = ''' + "'''" + r'''        if receipt.qos == QoS.AT_MOST_ONCE:
            self._loop.call_soon_threadsafe(
                self._async._spawn_callback,
                self._dispatch_publish,
                receipt.mid,
                None,
            )
        return info

    def _dispatch_publish(
        self, mid: int | None, error: BaseException | None
    ) -> None:
        if self.on_publish is None:
            return
        reason_code = 0 if error is None else 1
        self._safe_callback(
            self.on_publish,
            self,
            self._userdata,
            mid,
            reason_code,
            None,
        )

''' + "'''" + r'''
    if source.count(old) != 1:
        raise RuntimeError("Paho watcher marker changed")
    source = source.replace(old, new, 1)
    old = ''' + "'''" + r'''        except Exception:
            # A user callback must never kill the network loop.
            pass
''' + "'''" + r'''
    new = ''' + "'''" + r'''        except Exception as exc:
            loop = self._loop
            if loop is not None:
                context = {
                    "message": "mqttnext Paho-compatible callback failed",
                    "exception": exc,
                    "callback": cb,
                }
                if on_loop:
                    loop.call_exception_handler(context)
                else:
                    loop.call_soon_threadsafe(
                        loop.call_exception_handler, context
                    )
''' + "'''" + r'''
    if source.count(old) != 1:
        raise RuntimeError("Paho safe callback marker changed")
    text_path.write_text(source.replace(old, new, 1))
'''
replace_once("\n\ndef main() -> None:\n", patch_paho_source + "\n\ndef main() -> None:\n")
replace_once(
    "    write_sqlite_store()\n\n\nif __name__ == \"__main__\":\n",
    "    write_sqlite_store()\n    patch_paho()\n\n\nif __name__ == \"__main__\":\n",
)
path.write_text(text)
