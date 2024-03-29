import socket
import time
import struct
from threading import Thread
import signal
import sys
from scapy.all import *
import concurrent.futures

import colorize


def send_offer(UDP_IP):
    UDP_PORT = 13117

    # prefix = 0xfeedbeef, type = 0x02, port = 2086
    packet = struct.pack('!IBH', 0xfeedbeef, 0x2, 2086)

    # send offers for 10 seconds
    start_time = time.time()

    # init socket to address family (host, port) and for UDP connection on broadcast
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while time.time() - start_time < 10:
        sock.sendto(packet, (UDP_IP, UDP_PORT))
        time.sleep(1)

    sock.close()


def play(server_socket):
    teams = {}
    group1 = []
    group2 = []

    try:
        game = connect_to_clients(server_socket, teams, group1, group2)

        # if no teams don't start game
        if not game:
            return False

        for conn in teams.values():
            conn.sendall(b'Welcome to Keyboard Spamming Battle Royale.\n')
            conn.sendall('Group 1 :\n==\n{0}\n'.format('\n'.join(group1)).encode())
            conn.sendall('Group 2 :\n==\n{0}\n'.format('\n'.join(group2)).encode())

        # shutdown automatically
        with concurrent.futures.ThreadPoolExecutor() as executor:
            scores_futures = []
            for team, conn in teams.items():
                scores_futures.append(executor.submit(player_runnable, team=team, conn=conn, game_time=10))
                conn.sendall(b'START SPAMMING!!!!!\n')

            # Main thread computes results
            g1_res = 0
            g2_res = 0
            for res in concurrent.futures.as_completed(scores_futures):
                res = res.result()
                if res[0] in group1:
                    g1_res += res[1]
                else:
                    g2_res += res[1]

        game_over_msg = f'Game Over!\n Group 1 score: {g1_res}\n Group 2 score: {g2_res}\n'
        if g1_res > g2_res:
            game_over_msg += 'Winners : Group 1 !\n'
        elif g2_res > g1_res:
            game_over_msg += 'Winners : Group 2 !\n'
        else:
            game_over_msg += 'Tie !\n'

        for conn in teams.values():
            conn.sendall(game_over_msg.encode())

    except Exception as exc:
        print(colorize.colorize(exc, colorize.Colors.fatal))

    finally:
        time.sleep(len(teams))
        for conn in teams.values():
            conn.close()

    return True


def player_runnable(team, conn, game_time):
    score = 0
    start_time = time.time()
    while time.time() - start_time < game_time:
        readable, _, _ = select([conn], [], [])
        if readable:
            try:
                data = conn.recv(1024)
                if not data: break
                score += len(data)
            except Exception as exc:
                print(colorize.colorize(exc, colorize.Colors.fatal))
        time.sleep(0.5)
            
    return team, score


def connect_to_clients(sock, teams, group1, group2):
    BUFFER_SIZE = 1024

    # start game after 10 seconds
    start_time = time.time()
    group_index = 1
    while time.time() - start_time < 10:
        try:

            sock.settimeout(time.time() - start_time)
            conn, _ = sock.accept()
            conn.setblocking(False)

            data = conn.recv(BUFFER_SIZE)
            team_name = data.decode("utf-8")[:-1]
            print(colorize.colorize(f'Team: {team_name}', colorize.Colors.server))

            teams[team_name+"_"+str(group_index)] = conn

            # assign team to a group
            if group_index % 2 == 0:
                group2.append(team_name+"_"+str(group_index))
            else:
                group1.append(team_name+"_"+str(group_index))

            time.sleep(0.1)
            group_index += 1
        except Exception as exc:
            if str(exc) != 'timed out':
                print(colorize.colorize(exc, colorize.Colors.fatal))

    sock.settimeout(None)
    return group_index > 1


def quit(sig, frame):
    print('\nGoodbye!')
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, quit)
    signal.signal(signal.SIGTERM, quit)

    IP = None
    if len(sys.argv) > 1 and sys.argv[1] == '-t':
        IP = get_if_addr("eth2")
    else:
        IP = get_if_addr("eth1")

    TCP_PORT = 2086
    print(colorize.colorize(f'Server started, listening on IP address {IP}'))

    try:

        # init socket to address family (host, port) and for TCP connection
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((IP, TCP_PORT))

        # make socket a server's one, 5 is only advisory for num of connections
        server_socket.listen(5)

        while True:
            thread = Thread(target=send_offer, args=[IP])
            thread.start()
            game = play(server_socket)
            thread.join()
            if game:
                print('Game over, sending out offer requests...')
            else:
                print('Looking for players...')
            time.sleep(1)
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
