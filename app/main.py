import socket
import threading

def handle_client(conn, addr):
    print(f"Connection from {addr}")
    while True:
        data = conn.recv(1024)
        if not data:
            break  # Exit the loop if no data is received
        try:
            # Parse the request line and headers
            request, headers = data.decode().split("\r\n", 1)
            method, target = request.split(" ")[:2]
        except ValueError:
            # If parsing fails, send a bad request response
            response = b"HTTP/1.1 400 Bad Request\r\n\r\n"
            conn.sendall(response)
            break
        
        if target == "/":
            response = b"HTTP/1.1 200 OK\r\n\r\n"
        elif target.startswith("/echo/"):
            value = target.split("/echo/")[1]
            response = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(value)}\r\n\r\n{value}".encode()
        elif target == "/user-agent":
            # Extract User-Agent from the headers
            user_agent = None
            for header in headers.split("\r\n"):
                if header.startswith("User-Agent:"):
                    user_agent = header.split("User-Agent: ")[1]
                    break
            if user_agent:
                response_body = user_agent
            else:
                response_body = "No User-Agent found"
            response = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {len(response_body)}\r\n\r\n{response_body}".encode()
        else:
            response = b"HTTP/1.1 404 Not Found\r\n\r\n"
        
        conn.sendall(response)
    
    conn.close()  # Close the connection after handling the request
    print(f"Connection from {addr} closed")

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 4221))
        s.listen()
        print("Server is listening on port 4221...")
        
        while True:
            conn, addr = s.accept()
            # Create a new thread for each client connection
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.start()  # Start the thread

if __name__ == "__main__":
    main()
