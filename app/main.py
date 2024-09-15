import asyncio
import argparse
import re
import sys
import gzip
from asyncio.streams import StreamReader, StreamWriter
from pathlib import Path

GLOBALS = {}

def stderr(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)

def parse_request(content: bytes) -> tuple[str, str, dict[str, str], str]:
    first_line, *tail = content.split(b"\r\n")
    method, path, _ = first_line.split(b" ")
    headers: dict[str, str] = {}
    while (line := tail.pop(0)) != b"":
        key, value = line.split(b": ")
        headers[key.decode()] = value.decode()
    return method.decode(), path.decode(), headers, b"".join(tail).decode()

def make_response(
    status: int,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
) -> bytes:
    headers = headers or {}
    msg = {
        200: "OK",
        201: "Created",
        404: "Not Found",
    }

    header_str = "\r\n".join(
        [f"HTTP/1.1 {status} {msg[status]}"] +
        [f"{k}: {v}" for k, v in headers.items()] +
        [f"Content-Length: {len(body)}"]
    )
    
    # Add the final CRLF after headers before the body
    return f"{header_str}\r\n\r\n".encode() + body

async def handle_connection(reader: StreamReader, writer: StreamWriter) -> None:
    method, path, headers, body = parse_request(await reader.read(2**16))

    # Check if the client accepts gzip encoding
    accept_encoding = headers.get("Accept-Encoding", "")
    use_gzip = "gzip" in accept_encoding.lower()

    response_headers = {}
    if use_gzip:
        response_headers["Content-Encoding"] = "gzip"

    if re.fullmatch(r"/", path):
        writer.write(b"HTTP/1.1 200 OK\r\n\r\n")
        stderr(f"[OUT] /")
    elif re.fullmatch(r"/user-agent", path):
        ua = headers["User-Agent"]
        response_body = ua.encode()
        if use_gzip:
            response_body = gzip.compress(response_body)
        writer.write(make_response(200, {"Content-Type": "text/plain", **response_headers}, response_body))
        stderr(f"[OUT] user-agent {ua}")
    elif match := re.fullmatch(r"/echo/(.+)", path):
        msg = match.group(1).encode()  # Original message
        stderr(f"[OUT] echo {msg.decode()}")  # Log the uncompressed message

        if use_gzip:
            msg = gzip.compress(msg)  # Compress the message if gzip is accepted

        writer.write(make_response(200, {"Content-Type": "text/plain", **response_headers}, msg))
    elif match := re.fullmatch(r"/files/(.+)", path):
        p = Path(GLOBALS["DIR"]) / match.group(1)
        if method.upper() == "GET" and p.is_file():
            file_content = p.read_text().encode()
            if use_gzip:
                file_content = gzip.compress(file_content)
            writer.write(
                make_response(
                    200,
                    {"Content-Type": "application/octet-stream", **response_headers},
                    file_content,
                )
            )
        elif method.upper() == "POST":
            p.write_bytes(body.encode())
            writer.write(make_response(201, response_headers))
        else:
            writer.write(make_response(404, response_headers))
        stderr(f"[OUT] file {path}")
    else:
        writer.write(make_response(404, response_headers, b""))
        stderr(f"[OUT] 404")

    await writer.drain()
    writer.close()
    await writer.wait_closed()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default=".")
    args = parser.parse_args()

    GLOBALS["DIR"] = args.directory

    server = await asyncio.start_server(handle_connection, "localhost", 4221)
    async with server:
        stderr("Starting server...")
        stderr(f"--directory {GLOBALS['DIR']}")
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
