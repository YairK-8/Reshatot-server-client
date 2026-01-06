import socket
import threading

HOST = "0.0.0.0"
PORT = 5000

clients_lock = threading.Lock()
clients = {}          # username -> socket
pairs = {}            # username -> partner_username


def send_line(sock: socket.socket, text: str) -> None:
    try:
        sock.sendall((text + "\n").encode("utf-8"))
    except Exception:
        pass


def safe_close(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        sock.close()
    except Exception:
        pass


def cleanup_user(username: str) -> None:
    """Remove user from clients, and disconnect pairing safely."""
    with clients_lock:
        sock = clients.pop(username, None)
        partner = pairs.pop(username, None)

        # If the user had a partner, break the pairing on the other side too
        if partner is not None and pairs.get(partner) == username:
            pairs.pop(partner, None)
            partner_sock = clients.get(partner)
        else:
            partner_sock = None

    if partner_sock:
        send_line(partner_sock, f"[SERVER] {username} disconnected. Chat closed.")
    if sock:
        safe_close(sock)


def set_pair(a: str, b: str) -> None:
    with clients_lock:
        pairs[a] = b
        pairs[b] = a


def get_partner(username: str) -> str | None:
    with clients_lock:
        return pairs.get(username)


def get_socket(username: str) -> socket.socket | None:
    with clients_lock:
        return clients.get(username)


def list_users(except_name: str) -> list[str]:
    with clients_lock:
        return sorted([u for u in clients.keys() if u != except_name])


def handle_client(conn: socket.socket, addr) -> None:
    username = None
    f = conn.makefile("r", encoding="utf-8", newline="\n")

    try:
        send_line(conn, "[SERVER] Welcome! Enter your username:")
        username = f.readline().strip()

        if not username:
            send_line(conn, "[SERVER] Empty username. Bye.")
            return

        with clients_lock:
            if username in clients:
                send_line(conn, "[SERVER] Username already taken. Bye.")
                return
            clients[username] = conn

        send_line(conn, f"[SERVER] Hello {username}!")
        send_line(conn, "[SERVER] Commands:")
        send_line(conn, "  /users                -> list online users")
        send_line(conn, "  /chat <username>      -> start chat with user")
        send_line(conn, "  /leave                -> leave current chat")
        send_line(conn, "  /quit                 -> disconnect")
        send_line(conn, "[SERVER] Tip: after /chat, just type messages normally.")

        while True:
            line = f.readline()
            if not line:
                # client disconnected
                break

            msg = line.rstrip("\n")

            if not msg:
                continue

            if msg.startswith("/"):
                parts = msg.split(maxsplit=1)
                cmd = parts[0].lower()

                if cmd == "/users":
                    users = list_users(username)
                    if users:
                        send_line(conn, "[SERVER] Online: " + ", ".join(users))
                    else:
                        send_line(conn, "[SERVER] No other users online.")

                elif cmd == "/chat":
                    if len(parts) < 2 or not parts[1].strip():
                        send_line(conn, "[SERVER] Usage: /chat <username>")
                        continue

                    target = parts[1].strip()
                    if target == username:
                        send_line(conn, "[SERVER] You can't chat with yourself.")
                        continue

                    target_sock = get_socket(target)
                    if not target_sock:
                        send_line(conn, f"[SERVER] User '{target}' not found.")
                        continue

                    # Close previous chat if exists
                    old_partner = get_partner(username)
                    if old_partner:
                        with clients_lock:
                            if pairs.get(old_partner) == username:
                                pairs.pop(old_partner, None)
                            pairs.pop(username, None)

                        old_partner_sock = get_socket(old_partner)
                        if old_partner_sock:
                            send_line(old_partner_sock, f"[SERVER] {username} left the chat.")
                        send_line(conn, f"[SERVER] Left previous chat with {old_partner}.")

                    # If target is already in chat, we can choose to refuse
                    target_partner = get_partner(target)
                    if target_partner and target_partner != username:
                        send_line(conn, f"[SERVER] '{target}' is already chatting with '{target_partner}'.")
                        continue

                    set_pair(username, target)
                    send_line(conn, f"[SERVER] Chat started with {target}.")
                    send_line(target_sock, f"[SERVER] {username} started a chat with you. You are now connected.")

                elif cmd == "/leave":
                    partner = get_partner(username)
                    if not partner:
                        send_line(conn, "[SERVER] You're not in a chat.")
                        continue

                    with clients_lock:
                        if pairs.get(partner) == username:
                            pairs.pop(partner, None)
                        pairs.pop(username, None)

                    partner_sock = get_socket(partner)
                    if partner_sock:
                        send_line(partner_sock, f"[SERVER] {username} left the chat.")
                    send_line(conn, f"[SERVER] You left the chat with {partner}.")

                elif cmd == "/quit":
                    send_line(conn, "[SERVER] Bye.")
                    break

                else:
                    send_line(conn, "[SERVER] Unknown command.")
                continue

            # normal message -> forward to partner (if exists)
            partner = get_partner(username)
            if not partner:
                send_line(conn, "[SERVER] You're not in a chat. Use /users then /chat <username>.")
                continue

            partner_sock = get_socket(partner)
            if not partner_sock:
                # partner disappeared
                with clients_lock:
                    pairs.pop(username, None)
                send_line(conn, "[SERVER] Partner disconnected. Chat closed.")
                continue

            send_line(partner_sock, f"{username}: {msg}")

    except Exception:
        # keep it simple for students
        pass
    finally:
        if username:
            cleanup_user(username)
        else:
            safe_close(conn)
        try:
            f.close()
        except Exception:
            pass


def main() -> None:
    print(f"Server starting on {HOST}:{PORT} ...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(20)

    try:
        while True:
            conn, addr = s.accept()
            print(f"New connection from {addr}")
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\nServer shutting down.")
    finally:
        s.close()


if __name__ == "__main__":
    main()

