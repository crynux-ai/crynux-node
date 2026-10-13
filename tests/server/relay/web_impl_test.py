import json
import httpx
import pytest

from crynux_server.models import InMemoryModel, ModelFileEntry
from crynux_server.relay.exceptions import RelayError
from crynux_server.relay.web_impl import WebRelay
from crynux_server.task.error_report import TaskErrorReport

PRIVKEY = "0xa627246a109551432ac5db6535566af34fdddfaa11df17b8afd53eb987e209a2"
TASK_ID = bytes([1] * 32)
MODEL_FILE_A = ModelFileEntry(
    repository="org/model-a", revision="rev-a", format="diffusers"
)
MODEL_FILE_B = ModelFileEntry(
    repository="org/model-b",
    revision="rev-b",
    format="gguf",
    format_kwargs={"filename": "m.gguf"},
)


def make_relay(handler) -> WebRelay:
    relay = WebRelay(base_url="http://testserver", privkey=PRIVKEY)
    relay.client = httpx.AsyncClient(
        base_url="http://testserver", transport=httpx.MockTransport(handler)
    )
    return relay


async def test_http_error_propagates_without_retry():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"message": "internal server error"})

    relay = make_relay(handler)
    try:
        with pytest.raises(RelayError):
            await relay.get_task(TASK_ID)
        assert calls == 1

        with pytest.raises(RelayError):
            await relay.submit_task_score(TASK_ID, bytes([1] * 8))
        assert calls == 2
    finally:
        await relay.client.aclose()


async def test_transport_error_propagates_without_retry():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("connection failed", request=request)

    relay = make_relay(handler)
    try:
        with pytest.raises(httpx.ConnectError):
            await relay.node_get_current_task()
        assert calls == 1
    finally:
        await relay.client.aclose()


@pytest.mark.parametrize(
    ("execution_dtype", "expected_signed_input", "expected_body_dtype"),
    [
        (
            None,
            {
                "task_id_commitment": "0x" + TASK_ID.hex(),
                "score": "0x" + "01" * 8,
            },
            False,
        ),
        (
            "bfloat16",
            {
                "task_id_commitment": "0x" + TASK_ID.hex(),
                "score": "0x" + "01" * 8,
                "execution_dtype": "bfloat16",
            },
            True,
        ),
    ],
)
async def test_submit_score_signs_optional_execution_dtype(
    execution_dtype, expected_signed_input, expected_body_dtype
):
    captured = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"message": "success"})

    relay = make_relay(handler)
    signed_input = None

    def sign(input, timestamp=None):
        nonlocal signed_input
        signed_input = input
        return 1784851234, "0x" + "01" * 65

    relay.signer.sign = sign
    try:
        await relay.submit_task_score(
            TASK_ID, bytes([1] * 8), execution_dtype=execution_dtype
        )
    finally:
        await relay.client.aclose()

    assert signed_input == expected_signed_input
    assert captured is not None
    body = json.loads(captured.content)
    assert ("execution_dtype" in body) is expected_body_dtype
    if expected_body_dtype:
        assert body["execution_dtype"] == execution_dtype


async def test_task_diagnostic_request_contains_signed_fields():
    captured = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"message": "success"})

    relay = make_relay(handler)
    report = TaskErrorReport(
        node_address=str(relay.node_address),
        task_id_commitment="0x" + TASK_ID.hex(),
        task_args='{"prompt":"test"}',
        error_type="TaskExecutionError",
        message="worker failed",
        stack_trace="original traceback",
        gpu_count=2,
        gpu_model="2x NVIDIA GeForce RTX 4090",
        gpu_vram_mb=24564,
        executor_mode="tensor_parallel",
        captured_at=1784851200,
    )
    signed_input = None

    def sign(input, timestamp=None):
        nonlocal signed_input
        signed_input = input
        return 1784851234, "0x" + "01" * 65

    relay.signer.sign = sign
    try:
        await relay.report_task_diagnostic(report)
    finally:
        await relay.client.aclose()

    assert captured is not None
    assert captured.url.path == f"/v2/tasks/{report.task_id_commitment}/node_error"
    body = json.loads(captured.content)
    assert signed_input == {
        "node_address": report.node_address,
        "task_id_commitment": report.task_id_commitment,
        "task_args": report.task_args,
        "error_type": report.error_type,
        "message": report.message,
        "stack_trace": report.stack_trace,
        "gpu_count": report.gpu_count,
        "gpu_model": report.gpu_model,
        "gpu_vram_mb": report.gpu_vram_mb,
        "executor_mode": report.executor_mode,
    }
    for field in (
        "node_address",
        "task_id_commitment",
        "task_args",
        "error_type",
        "message",
        "stack_trace",
        "gpu_count",
        "gpu_model",
        "gpu_vram_mb",
        "executor_mode",
        "captured_at",
        "timestamp",
        "signature",
    ):
        assert field in body
    assert isinstance(body["captured_at"], int)
    assert "capture_time" not in body


async def test_get_balance_uses_v2_signature_authorization():
    captured = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"data": "123"})

    relay = make_relay(handler)
    signed_input = None

    def sign(input, timestamp=None):
        nonlocal signed_input
        signed_input = input
        return 1784851234, "0x" + "01" * 65

    relay.signer.sign = sign
    try:
        balance = await relay.get_balance()
    finally:
        await relay.client.aclose()

    assert balance == 123
    assert captured is not None
    assert captured.url.path == f"/v2/relay_account/{relay.node_address}/balance"
    assert dict(captured.url.params) == {
        "timestamp": "1784851234",
        "signature": "0x" + "01" * 65,
    }
    assert signed_input == {"address": relay.node_address}


async def test_node_sync_capabilities_reports_complete_signed_inventory():
    captured = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"message": "success"})

    relay = make_relay(handler)
    signed_input = None

    def sign(input, timestamp=None):
        nonlocal signed_input
        signed_input = input
        return 1784851234, "0x" + "01" * 65

    relay.signer.sign = sign
    model_files = [MODEL_FILE_A, MODEL_FILE_B]
    model_files_data = [entry.model_dump() for entry in model_files]
    try:
        await relay.node_sync_capabilities(
            gpu_name="2x NVIDIA GeForce RTX 4090 TP+docker",
            gpu_vram=48,
            model_files=model_files,
            version="3.2.0",
        )
    finally:
        await relay.client.aclose()

    assert captured is not None
    assert captured.url.path == f"/v2/node/{relay.node_address}/capabilities"
    assert signed_input == {
        "address": relay.node_address,
        "gpu_name": "2x NVIDIA GeForce RTX 4090 TP+docker",
        "gpu_vram": 48,
        "model_files": model_files_data,
        "version": "3.2.0",
    }
    body = json.loads(captured.content)
    assert body == {
        "gpu_name": "2x NVIDIA GeForce RTX 4090 TP+docker",
        "gpu_vram": 48,
        "model_files": model_files_data,
        "version": "3.2.0",
        "timestamp": 1784851234,
        "signature": "0x" + "01" * 65,
    }
    assert body["model_files"][0] == {
        "source_type": "huggingface",
        "repository": "org/model-a",
        "revision": "rev-a",
        "format": "diffusers",
        "format_kwargs": {},
    }


async def test_node_join_reports_signed_model_files():
    captured = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"message": "success"})

    relay = make_relay(handler)
    signed_input = None

    def sign(input, timestamp=None):
        nonlocal signed_input
        signed_input = input
        return 1784851234, "0x" + "01" * 65

    relay.signer.sign = sign
    model_files_data = [MODEL_FILE_A.model_dump()]
    try:
        await relay.node_join(
            network="dymension",
            gpu_name="RTX 4090+docker",
            gpu_vram=24,
            model_files=[MODEL_FILE_A],
            version="3.2.0",
            staking_amount=10,
        )
    finally:
        await relay.client.aclose()

    assert captured is not None
    assert captured.url.path == f"/v2/node/{relay.node_address}/join"
    assert signed_input is not None
    assert signed_input["model_files"] == model_files_data
    assert "model_ids" not in signed_input
    body = json.loads(captured.content)
    assert body["model_files"] == model_files_data
    assert "model_ids" not in body


async def test_node_report_model_downloaded_sends_model_file():
    captured = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"message": "success"})

    relay = make_relay(handler)
    signed_input = None

    def sign(input, timestamp=None):
        nonlocal signed_input
        signed_input = input
        return 1784851234, "0x" + "01" * 65

    relay.signer.sign = sign
    try:
        await relay.node_report_model_downloaded(MODEL_FILE_B)
    finally:
        await relay.client.aclose()

    assert captured is not None
    assert captured.url.path == f"/v1/node/{relay.node_address}/model"
    assert signed_input == {
        "address": relay.node_address,
        "model_file": MODEL_FILE_B.model_dump(),
    }
    assert json.loads(captured.content) == {
        "model_file": MODEL_FILE_B.model_dump(),
        "timestamp": 1784851234,
        "signature": "0x" + "01" * 65,
    }


@pytest.mark.parametrize("with_model", [True, False])
async def test_node_report_in_memory_model(with_model):
    captured = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"message": "success"})

    relay = make_relay(handler)
    signed_input = None

    def sign(input, timestamp=None):
        nonlocal signed_input
        signed_input = input
        return 1784851234, "0x" + "01" * 65

    relay.signer.sign = sign
    model = (
        InMemoryModel(
            model_cache_hash="ab" * 32,
            model_cache_config={"dtype": "auto", "task_kind": "image"},
            model_files=[MODEL_FILE_A],
            execution_dtype="bfloat16",
        )
        if with_model
        else None
    )
    model_data = model.model_dump() if model is not None else None
    try:
        await relay.node_report_in_memory_model(model)
    finally:
        await relay.client.aclose()

    assert captured is not None
    assert captured.url.path == f"/v2/node/{relay.node_address}/in_memory_model"
    assert signed_input == {"address": relay.node_address, "model": model_data}
    assert json.loads(captured.content) == {
        "model": model_data,
        "timestamp": 1784851234,
        "signature": "0x" + "01" * 65,
    }
