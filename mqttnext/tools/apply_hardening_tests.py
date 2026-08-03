from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(content).lstrip())


def main() -> None:
    write(
        "tests/unit/test_effect_atomicity.py",
        r'''
        """Atomic effect transfer and bounded callback lifecycle."""

        from __future__ import annotations

        import asyncio

        import pytest

        from mqttnext.api.async_client import AsyncClient
        from mqttnext.enums import ConnectionState
        from mqttnext.protocol.engine import EffectKind
        from mqttnext.types import Message


        async def test_cancelled_backpressure_keeps_send_effect_for_same_connection() -> None:
            client = AsyncClient(
                client_id="effect-cancel",
                max_outbound_messages=1,
                max_outbound_bytes=1,
            )
            client._engine.state = ConnectionState.CONNECTED
            await client._enqueue_outbound(b"x")

            publishing = asyncio.create_task(
                client.publish("effect/t", b"payload", qos=0)
            )
            for _ in range(100):
                if client._outbound_waiters:
                    break
                await asyncio.sleep(0)
            assert client._outbound_waiters == 1

            publishing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await publishing
            assert any(
                effect.kind is EffectKind.SEND
                for effect in client._pending_effects
            )

            blocked = client._outbound.get_nowait()
            client._outbound.task_done()
            client._outbound_bytes -= len(blocked)
            async with client._outbound_space:
                client._outbound_space.notify_all()

            await client._drain_effects()
            assert not client._pending_effects
            assert client._outbound.qsize() == 1


        async def test_callback_exception_reaches_loop_exception_handler() -> None:
            client = AsyncClient(client_id="callback-error")
            loop = asyncio.get_running_loop()
            contexts: list[dict[str, object]] = []
            previous = loop.get_exception_handler()
            loop.set_exception_handler(lambda _loop, context: contexts.append(context))

            def fail(_message: Message) -> None:
                raise RuntimeError("callback failed")

            try:
                await client._enqueue_callback(
                    fail, Message(topic="t", payload=b"x")
                )
                await asyncio.wait_for(client._callback_queue.join(), timeout=1.0)
                assert len(contexts) == 1
                assert isinstance(contexts[0].get("exception"), RuntimeError)
                assert contexts[0].get("callback") is fail
            finally:
                loop.set_exception_handler(previous)
                await client._shutdown_callback_worker(drain=False)


        async def test_force_close_stops_callback_worker() -> None:
            client = AsyncClient(
                client_id="callback-close",
                callback_shutdown_timeout=0.05,
            )
            started = asyncio.Event()
            release = asyncio.Event()

            async def slow(_message: Message) -> None:
                started.set()
                await release.wait()

            await client._enqueue_callback(slow, Message(topic="t", payload=b"x"))
            await started.wait()
            assert client._callback_worker_task is not None

            await client._force_close()
            assert client._callback_worker_task is None
        ''',
    )

    write(
        "tests/unit/test_message_delivery.py",
        r'''
        """Message delivery modes, ordering and stream lifecycle."""

        from __future__ import annotations

        import asyncio

        import pytest

        from mqttnext.api.async_client import AsyncClient
        from mqttnext.protocol.engine import EffectKind, EngineEffect
        from mqttnext.types import Message


        async def _deliver(client: AsyncClient, payload: bytes = b"x") -> None:
            await client._apply_effect(
                EngineEffect(
                    kind=EffectKind.MESSAGE,
                    data=Message(topic="delivery/test", payload=payload),
                ),
                nowait=False,
            )


        async def test_auto_callback_does_not_fill_iterator_queue() -> None:
            client = AsyncClient(
                client_id="delivery-auto",
                max_pending_messages=1,
                message_delivery="auto",
            )
            received: list[bytes] = []
            client.on_message = lambda message: received.append(message.payload)

            for index in range(5):
                await _deliver(client, str(index).encode())
            await asyncio.wait_for(client._callback_queue.join(), timeout=1.0)

            assert received == [b"0", b"1", b"2", b"3", b"4"]
            assert client._messages.empty()
            await client._shutdown_callback_worker(drain=False)


        async def test_iterator_mode_ignores_callback() -> None:
            client = AsyncClient(client_id="delivery-iterator", message_delivery="iterator")
            received: list[bytes] = []
            client.on_message = lambda message: received.append(message.payload)

            await _deliver(client)
            assert received == []
            assert client._messages.get_nowait().payload == b"x"


        async def test_both_mode_delivers_to_callback_and_iterator() -> None:
            client = AsyncClient(client_id="delivery-both", message_delivery="both")
            received: list[bytes] = []
            client.on_message = lambda message: received.append(message.payload)

            await _deliver(client)
            await asyncio.wait_for(client._callback_queue.join(), timeout=1.0)
            assert received == [b"x"]
            assert client._messages.get_nowait().payload == b"x"
            await client._shutdown_callback_worker(drain=False)


        async def test_stream_drains_messages_before_closed() -> None:
            client = AsyncClient(
                client_id="delivery-close",
                max_pending_messages=2,
                message_delivery="iterator",
            )
            await _deliver(client, b"1")
            await _deliver(client, b"2")
            client._closed.set()
            client._message_ready.set()

            received = [message.payload async for message in client.messages()]
            assert received == [b"1", b"2"]


        async def test_explicit_reconnect_resets_closed_message_stream() -> None:
            client = AsyncClient(client_id="delivery-reset", max_pending_messages=2)
            original = client._messages
            client._closed.set()
            client._message_ready.set()

            client._reset_message_stream()

            assert client._messages is not original
            assert client._messages.maxsize == 2
            assert client._messages.empty()
            assert not client._closed.is_set()


        def test_invalid_message_delivery_rejected() -> None:
            with pytest.raises(ValueError, match="message_delivery"):
                AsyncClient(message_delivery="invalid")  # type: ignore[arg-type]
        ''',
    )

    write(
        "tests/unit/test_delivery_backpressure.py",
        r'''
        """Application delivery backpressure is bounded and explicit."""

        from __future__ import annotations

        import asyncio

        import pytest

        from mqttnext.api.async_client import AsyncClient
        from mqttnext.errors import MessageDeliveryError
        from mqttnext.protocol.engine import EffectKind, EngineEffect
        from mqttnext.types import Message


        async def test_iterator_queue_timeout_is_explicit() -> None:
            client = AsyncClient(
                message_delivery="iterator",
                max_pending_messages=1,
                delivery_timeout=0.01,
            )
            client._messages.put_nowait(Message(topic="full", payload=b"x"))

            with pytest.raises(MessageDeliveryError, match="Iterator delivery queue"):
                await client._apply_effect(
                    EngineEffect(
                        kind=EffectKind.MESSAGE,
                        data=Message(topic="overflow", payload=b"x"),
                    ),
                    nowait=False,
                )


        async def test_callback_queue_timeout_is_explicit_and_bounded() -> None:
            client = AsyncClient(
                message_delivery="callback",
                max_pending_callbacks=1,
                delivery_timeout=0.01,
                callback_shutdown_timeout=0.01,
            )
            started = asyncio.Event()
            release = asyncio.Event()

            async def slow(_message: Message) -> None:
                started.set()
                await release.wait()

            await client._enqueue_callback(slow, Message(topic="one", payload=b"x"))
            await started.wait()
            await client._enqueue_callback(slow, Message(topic="two", payload=b"x"))

            with pytest.raises(MessageDeliveryError, match="Callback delivery queue"):
                await client._enqueue_callback(
                    slow, Message(topic="three", payload=b"x")
                )
            await client._shutdown_callback_worker(drain=False)


        async def test_callback_worker_preserves_order() -> None:
            client = AsyncClient(max_pending_callbacks=8)
            seen: list[int] = []

            async def callback(value: int) -> None:
                await asyncio.sleep(0)
                seen.append(value)

            for value in range(8):
                await client._enqueue_callback(callback, value)
            await asyncio.wait_for(client._callback_queue.join(), timeout=1.0)

            assert seen == list(range(8))
            await client._shutdown_callback_worker(drain=False)
        ''',
    )

    write(
        "tests/unit/test_reconnect_stale_effects.py",
        r'''
        """Wire effects from a dead transport never cross a connection epoch."""

        from __future__ import annotations

        import asyncio

        import pytest

        from mqttnext.api.async_client import AsyncClient
        from mqttnext.codec.buffer import IncrementalDecoder
        from mqttnext.enums import ConnectionState, PacketType
        from mqttnext.packets import PublishPacket, encode_frame
        from mqttnext.protocol.engine import EffectKind


        class ConnackTransport:
            def __init__(self, *, session_present: bool) -> None:
                self._rx: asyncio.Queue[bytes] = asyncio.Queue()
                self._decoder = IncrementalDecoder()
                self._closing = False
                self.session_present = session_present
                self.written: list[bytes] = []

            async def write(self, data: bytes) -> None:
                self.written.append(data)
                self._decoder.feed(data)
                for raw in self._decoder.drain_packets():
                    if raw.packet_type is PacketType.CONNECT:
                        flags = 1 if self.session_present else 0
                        self._rx.put_nowait(
                            encode_frame(PacketType.CONNACK, 0, bytes([flags, 0]))
                        )

            async def read(self, n: int = 65536) -> bytes:
                return await self._rx.get()

            async def close(self) -> None:
                self._closing = True
                self._rx.put_nowait(b"")

            def is_closing(self) -> bool:
                return self._closing


        async def _cancel_send_under_backpressure(client: AsyncClient) -> int:
            client._engine.state = ConnectionState.CONNECTED
            await client._enqueue_outbound(b"x")
            publishing = asyncio.create_task(
                client.publish("audit/stale", b"payload", qos=1)
            )
            for _ in range(100):
                if client._outbound_waiters:
                    break
                await asyncio.sleep(0)
            assert client._outbound_waiters == 1
            publishing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await publishing
            assert any(
                effect.kind is EffectKind.SEND
                for effect in client._pending_effects
            )
            mid = next(iter(client._receipts))
            client._engine.notify_transport_closed()
            client._engine.take_effects()
            return mid


        def _packets(written: list[bytes]):
            decoder = IncrementalDecoder()
            packets = []
            for data in written:
                decoder.feed(data)
                packets.extend(decoder.drain_packets())
            return packets


        async def test_clean_reconnect_does_not_send_failed_old_publish() -> None:
            client = AsyncClient(
                client_id="audit-clean",
                max_outbound_messages=1,
                max_outbound_bytes=1,
            )
            mid = await _cancel_send_under_backpressure(client)
            transport = ConnackTransport(session_present=False)

            async def factory(
                host: str, port: int, *, ssl: object = None
            ) -> ConnackTransport:
                return transport

            client._transport_factory = factory
            await client.connect("fake", timeout=1.0)
            await asyncio.sleep(0)

            assert [packet.packet_type for packet in _packets(transport.written)] == [
                PacketType.CONNECT
            ]
            assert mid not in client._receipts
            await client._force_close()


        async def test_resumed_session_rebuilds_exactly_one_publish() -> None:
            client = AsyncClient(
                client_id="audit-resume",
                clean_start=False,
                max_outbound_messages=1,
                max_outbound_bytes=1,
            )
            await _cancel_send_under_backpressure(client)
            transport = ConnackTransport(session_present=True)

            async def factory(
                host: str, port: int, *, ssl: object = None
            ) -> ConnackTransport:
                return transport

            client._transport_factory = factory
            await client.connect("fake", timeout=1.0)
            packets = []
            for _ in range(100):
                packets = _packets(transport.written)
                if sum(p.packet_type is PacketType.PUBLISH for p in packets) == 1:
                    break
                await asyncio.sleep(0)

            publishes = [
                PublishPacket.decode(packet.flags, packet.remaining)
                for packet in packets
                if packet.packet_type is PacketType.PUBLISH
            ]
            assert len(publishes) == 1
            assert publishes[0].dup is True
            await client._force_close()
        ''',
    )

    write(
        "tests/unit/test_sqlite_store.py",
        r'''
        """SqliteInflightStore durability, migration and hot-path tests."""

        from __future__ import annotations

        import base64
        from pathlib import Path

        from mqttnext.enums import InboundQoSState, OutboundQoSState, QoS
        from mqttnext.persistence.sqlite import SqliteInflightStore
        from mqttnext.types import InboundMessage, OutboundMessage, Properties


        def outbound(mid: int = 7) -> OutboundMessage:
            return OutboundMessage(
                mid=mid,
                topic="a/b",
                payload=b"payload",
                qos=QoS.AT_LEAST_ONCE,
                retain=False,
                state=OutboundQoSState.WAIT_PUBACK,
                dup=False,
            )


        def test_sqlite_outbound_roundtrip_and_blob_storage(tmp_path: Path) -> None:
            path = tmp_path / "inflight.db"
            store = SqliteInflightStore(path)
            store.put_out(outbound())
            storage_type = store._conn.execute(
                "SELECT typeof(payload) FROM outbound WHERE mid=7"
            ).fetchone()[0]
            assert storage_type == "blob"
            store.close()

            reopened = SqliteInflightStore(path)
            got = reopened.get_out(7)
            assert got is not None
            assert got.topic == "a/b"
            assert got.payload == b"payload"
            assert got.state is OutboundQoSState.WAIT_PUBACK
            assert reopened.pop_out(7) is not None
            assert reopened.get_out(7) is None
            reopened.close()


        def test_legacy_base64_text_payload_is_read_lazily(tmp_path: Path) -> None:
            store = SqliteInflightStore(tmp_path / "legacy.db")
            store.put_out(outbound())
            store._conn.execute(
                "UPDATE outbound SET payload=? WHERE mid=7",
                (base64.b64encode(b"legacy").decode("ascii"),),
            )
            store._conn.commit()

            got = store.get_out(7)
            assert got is not None
            assert got.payload == b"legacy"
            store.close()


        def test_batch_commits_once(tmp_path: Path) -> None:
            store = SqliteInflightStore(tmp_path / "batch.db")
            trace: list[str] = []
            store._conn.set_trace_callback(trace.append)

            with store.batch():
                store.put_out(outbound(1))
                store.put_out(outbound(2))

            assert sum(statement == "COMMIT" for statement in trace) == 1
            assert [message.mid for message in store.out_items()] == [1, 2]
            store.close()


        def test_update_out_only_touches_hot_state_columns(tmp_path: Path) -> None:
            store = SqliteInflightStore(tmp_path / "hot.db")
            store.put_out(outbound())
            changed = OutboundMessage(
                mid=7,
                topic="must-not-rewrite",
                payload=b"must-not-rewrite",
                qos=QoS.EXACTLY_ONCE,
                retain=True,
                state=OutboundQoSState.WAIT_PUBCOMP,
                dup=True,
            )
            store.update_out(changed)

            got = store.get_out(7)
            assert got is not None
            assert got.topic == "a/b"
            assert got.payload == b"payload"
            assert got.qos is QoS.AT_LEAST_ONCE
            assert got.state is OutboundQoSState.WAIT_PUBCOMP
            assert got.dup is True
            store.close()


        def test_sqlite_properties_binary_and_user_property(tmp_path: Path) -> None:
            store = SqliteInflightStore(tmp_path / "props.db")
            props = Properties()
            props.set("correlation_data", b"\x00\xffbinary")
            props.set("content_type", "application/octet-stream")
            props.add_user_property("k", "v")
            props.add_user_property("k2", "v2")
            props.values["subscription_identifier"] = [11, 22]
            msg = OutboundMessage(
                mid=9,
                topic="p",
                payload=b"x",
                qos=QoS.EXACTLY_ONCE,
                retain=False,
                state=OutboundQoSState.WAIT_PUBREC,
                properties=props,
            )
            store.put_out(msg)
            got = store.get_out(9)
            assert got is not None
            assert got.properties is not None
            assert got.properties.get("correlation_data") == b"\x00\xffbinary"
            assert got.properties.get("content_type") == "application/octet-stream"
            assert got.properties.get("user_property") == [("k", "v"), ("k2", "v2")]
            assert got.properties.get("subscription_identifier") == [11, 22]
            store.close()


        def test_sqlite_inbound_manual_ack_flag(tmp_path: Path) -> None:
            store = SqliteInflightStore(tmp_path / "in.db")
            msg = InboundMessage(
                mid=3,
                topic="t",
                payload=b"x",
                qos=QoS.EXACTLY_ONCE,
                retain=False,
                state=InboundQoSState.WAIT_PUBREL,
                delivered=True,
                user_acked=True,
            )
            store.put_in(msg)
            got = store.get_in(3)
            assert got is not None
            assert got.user_acked is True
            store.clear_in()
            assert store.get_in(3) is None
            store.close()
        ''',
    )

    tls = ROOT / "tests/unit/test_tls.py"
    text = tls.read_text()
    if "test_tls_rejects_hostname_mismatch" not in text:
        tls.write_text(
            text
            + r'''


async def test_tls_rejects_hostname_mismatch(tmp_path: Path) -> None:
    key, cert = _make_certs(tmp_path)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert, key)

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0, ssl=server_ctx)
    assert server.sockets
    port = server.sockets[0].getsockname()[1]
    async with server:
        client_ctx = ssl.create_default_context()
        client_ctx.load_verify_locations(cert)
        client = AsyncClient(client_id="tls-hostname")
        with pytest.raises(ssl.CertificateError):
            await client.connect(
                "localhost.invalid",
                port,
                ssl=client_ctx,
                timeout=5.0,
            )
        assert not client.is_connected
'''
        )


if __name__ == "__main__":
    main()
