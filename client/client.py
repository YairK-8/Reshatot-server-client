
import socket
import threading
import sys

HOST = "127.0.0.1"   # ?? ???? ?? ???? ????
PORT = 5000


def recv_loop(sock: socket.socket) -> None:
    f = sock.makefile("r", encoding="utf-8", newline="\n")
    try:
        while True:
            line = f.readline()
            if not line:
                print("\n[Disconnected from server]")
                break
            print(line.rstrip("\n"))
    except Exception:
        pass
    finally:
        try:
            f.close()
        except Exception:
            pass


def main() -> None:
    print(f"Connecting to {HOST}:{PORT} ...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    t = threading.Thread(target=recv_loop, args=(sock,), daemon=True)
    t.start()

    try:
        while True:
            user_input = input()
            sock.sendall((user_input + "\n").encode("utf-8"))
            if user_input.strip().lower() == "/quit":
                break
    except (KeyboardInterrupt, EOFError):
        try:
            sock.sendall(b"/quit\n")
        except Exception:
            pass
    finally:
        try:
            sock.close()
        except Exception:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
