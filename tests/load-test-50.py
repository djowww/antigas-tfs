#!/usr/bin/env python3
"""Bounded 50-session integration load test for the isolated Antigas staging world.

Run only on the staging VPS. It refuses to run unless the staging unit, loopback
listener, staging environment file, and dedicated test schema are all present.
All generated accounts use a reserved ID range and .test.invalid email addresses.
"""

if not __debug__:
    raise SystemExit('Python optimization (-O) disables validation assertions; refusing to run this tool.')

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import struct
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from load_test_protocol import Client, string
from staging_safety import require_staging_target

DB = "antigas_load_v37"
PORT = 7176
ACCOUNT_BASE = 980001
PLAYER_COUNT = 50
NETWORK_ONLY = False
MAINTENANCE_WINDOW = False
ACCOUNT_END = ACCOUNT_BASE + PLAYER_COUNT - 1
RSA_PUBLIC = Path("/opt/antigas-security-v26/rsa-public.json")
MARKET_OPCODE = b"\x32\xca"
HUNT_POINTS = [
    (32503, 32180, 7), (32505, 32180, 7),
    (32297, 32054, 7), (32299, 32054, 7),
    (32208, 32100, 7), (32210, 32100, 7),
    (32810, 32224, 7), (32813, 32224, 7),
    (32637, 32600, 7), (32639, 32600, 7),
]
THAIS_TEMPLE = (32369, 32241, 7)
created = []
clients = []
stop = threading.Event()
keepalive_threads = []
connection_lock = threading.Lock()
last_connection = 0.0


def run(args, *, text=True):
    return subprocess.check_output(args, text=text, timeout=20).strip()


def sql(query):
    return run(["mariadb", "--batch", "--skip-column-names", DB, "-e", query])


def account_name(index):
    return f"LoadV37-{index + 1:03d}"


def account_email(index):
    return f"load-v37-{index + 1:03d}@test.invalid"


def assert_isolated_staging(require_production_active=True):
    assert run(["systemctl", "is-active", "imperium772-staging"]) == "active"
    envfiles = run(["systemctl", "show", "imperium772-staging", "-p", "EnvironmentFiles", "--value"])
    assert "/etc/imperium772-staging.env" in envfiles and "/etc/imperium772.env" not in envfiles
    env = {}
    for line in Path("/etc/imperium772-staging.env").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    assert env.get("TFS_DB_NAME") == DB, "staging points to a different database"
    assert env.get("TFS_DB_USER") == DB, "staging does not use its dedicated SQL user"
    listeners = run(["ss", "-ltn" ])
    assert "127.0.0.1:7175" in listeners and "127.0.0.1:7176" in listeners
    public_bindings = ("0.0.0.0:7175", "0.0.0.0:7176", "[::]:7175", "[::]:7176", "*:7175", "*:7176")
    assert not any(binding in listeners for binding in public_bindings), "staging port is not loopback-only"
    production_state = run(["systemctl", "show", "imperium772", "-p", "ActiveState", "--value"])
    expected_production_state = "active" if require_production_active else "inactive"
    assert production_state == expected_production_state, (
        f"production must be {expected_production_state} for this test; got {production_state}"
    )
    assert sql("SELECT COUNT(*) FROM accounts WHERE id BETWEEN 980001 AND 980050") == "0", (
        "reserved synthetic account range is not clean"
    )


def matching_player_ids():
    raw = sql(
        "SELECT id FROM players WHERE account_id BETWEEN 980001 AND 980050 "
        "AND name REGEXP '^LoadV37-[0-9]{3}$'"
    )
    return [int(value) for value in raw.splitlines() if value]


def cleanup_test_rows():
    ids = matching_player_ids()
    if ids:
        id_list = ",".join(map(str, ids))
        online = int(sql(f"SELECT COUNT(*) FROM players_online WHERE player_id IN ({id_list})"))
        if online:
            raise RuntimeError(f"refusing to delete {online} synthetic characters still online")
        for table in ("market_requests", "market_history", "market_claims", "market_offers"):
            sql(f"DELETE FROM {table} WHERE player_guid IN ({id_list})" if table != "market_offers"
                else f"DELETE FROM {table} WHERE owner_guid IN ({id_list})")
        sql(f"DELETE FROM players WHERE id IN ({id_list})")
    sql(
        "DELETE FROM accounts WHERE id BETWEEN 980001 AND 980050 "
        "AND email REGEXP '^load-v37-[0-9]{3}@test[.]invalid$'"
    )


def wait_for_logout(player_ids, timeout=60):
    if not player_ids:
        return
    id_list = ",".join(map(str, player_ids))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        online = int(sql(f"SELECT COUNT(*) FROM players_online WHERE player_id IN ({id_list})"))
        if online == 0:
            return
        time.sleep(1)
    raise RuntimeError(f"{online} synthetic sessions did not log out within {timeout}s")


def seed_player(index, role):
    account_id = ACCOUNT_BASE + index
    name = account_name(index)
    email = account_email(index)
    password = secrets.token_urlsafe(20)
    password_hash = hashlib.sha1(password.encode("utf-8")).hexdigest()
    account_type = 1
    group_id = 1
    if role == "hunter":
        x, y, z = HUNT_POINTS[index]
    else:
        x, y, z = THAIS_TEMPLE
    group_count = PLAYER_COUNT // 5
    buyer_index = index - 2 * group_count
    bank = 50000 if role == "buyer" and buyer_index < max(1, group_count // 2) else 0
    level, experience, sword_skill = (8, 4200, 70) if role == "hunter" else (8, 4200, 20)
    # Durable synthetic hunters must survive the paced login ramp before
    # combat begins. This is a capacity fixture, not a combat-balance test.
    health = 5000 if role == "hunter" else 150

    sql(
        "INSERT INTO accounts(id,password,type,email) VALUES "
        f"({account_id},'{password_hash}',{account_type},'{email}')"
    )
    sql(
        "INSERT INTO players(name,account_id,group_id,level,experience,health,healthmax,"
        "conditions,comment,cap,town_id,posx,posy,posz,looktype,lastlogin,balance,skill_sword) VALUES "
        f"('{name}',{account_id},{group_id},{level},{experience},{health},{health},'','',100000,2,"
        f"{x},{y},{z},128,1,{bank},{sword_skill})"
    )
    player_id = int(sql(f"SELECT id FROM players WHERE account_id={account_id}"))
    sql(
        f"INSERT INTO player_items(player_id,pid,sid,itemtype,count,attributes) "
        f"VALUES({player_id},3,101,2854,1,'')"
    )

    if role == "hunter":
        sql(
            "INSERT INTO player_items(player_id,pid,sid,itemtype,count,attributes) "
            f"VALUES({player_id},5,102,3264,1,'')"
        )
    elif role == "seller":
        sql(
            "INSERT INTO player_items(player_id,pid,sid,itemtype,count,attributes) "
            f"VALUES({player_id},101,102,3578,2,'')"
        )
    elif role == "buyer" and buyer_index >= max(1, group_count // 2):
        sql(
            "INSERT INTO player_items(player_id,pid,sid,itemtype,count,attributes) "
            f"VALUES({player_id},101,102,5130,50,'')"
        )
    created.append({"index": index, "account": account_id, "name": name,
                    "password": password, "player": player_id, "role": role})
    return created[-1]


class StageClient(Client):
    def __init__(self, account, password, name):
        global last_connection
        self.key = struct.unpack("<IIII", secrets.token_bytes(16))
        # Ban::acceptConnection blocks bursts from the same source IP. Space
        # openings while retaining every established session for real load.
        with connection_lock:
            time.sleep(max(0, 0.75 - (time.monotonic() - last_connection)))
            self.sock = socket.create_connection(("127.0.0.1", PORT), timeout=30)
            last_connection = time.monotonic()
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        block = (b"\0" + struct.pack("<IIII", *self.key) + b"\0"
                 + struct.pack("<I", account) + string(name) + string(password))
        modulus = int(json.loads(RSA_PUBLIC.read_text())["modulus"])
        encrypted = pow(int.from_bytes(block.ljust(128, b"\0"), "big"), 65537, modulus).to_bytes(128, "big")
        packet = b"\x0a" + struct.pack("<HH", 11, 772) + encrypted
        self.sock.sendall(struct.pack("<H", len(packet)) + packet)
        self.keepalive_error = None
        self.buffer = b""
        self.io_lock = threading.RLock()
        try:
            self.initial = self.collect(3)
        except Exception:
            self.sock.close()
            raise
        # Welcome text can precede failed placement. Require the self-login
        # header too; the world registry is checked separately after login.
        self_login = re.search(rb"\x0a(.{4})\x32\x00[\x00\x01]", self.initial, re.DOTALL)
        if b"Welcome to Antigas" not in self.initial or self_login is None:
            self.sock.close()
            sample = self.initial[:80].hex()
            raise RuntimeError(
                f"game login rejected for synthetic account {account}; "
                f"response_bytes={len(self.initial)} sample_hex={sample}"
            )

        self.creature_id = struct.unpack("<I", self_login.group(1))[0]

    def send(self, data):
        with self.io_lock:
            return super().send(data)

    def collect(self, seconds=2):
        with self.io_lock:
            return super().collect(seconds)

    def close(self):
        try:
            self.send(b"\x14")
            self.collect(0.2)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass

    def keepalive(self, stop):
        while not stop.is_set():
            try:
                self.send(bytes([0x1E]))
                # Only request handlers read: background reads stole receipts.
            except (OSError, socket.timeout) as error:
                self.keepalive_error = str(error)
                return
            stop.wait(2)


def find_hunt_target(data):
    for name in (b"rat", b"cave rat", b"spider"):
        marker = struct.pack("<H", len(name)) + name
        offset = 0
        while True:
            name_at = data.lower().find(marker, offset)
            if name_at < 0:
                break
            offset = name_at + 1
            start = name_at - 10
            if start < 0 or struct.unpack_from("<H", data, start)[0] != 0x61:
                continue
            creature_id = struct.unpack_from("<I", data, start + 6)[0]
            if creature_id:
                return creature_id, name.decode("ascii")
    return None


def decode_market(data):
    packets = []
    offset = 0
    while True:
        start = data.find(MARKET_OPCODE, offset)
        if start < 0:
            return packets
        offset = start + 2
        if len(data) < start + 4:
            continue
        length = struct.unpack_from("<H", data, start + 2)[0]
        end = start + 4 + length
        if end > len(data):
            continue
        try:
            packets.append(json.loads(data[start + 4:end]))
        except (ValueError, UnicodeDecodeError):
            pass


def market_request(client, action, data=None, *, expect_ok=None, timeout=4):
    if expect_ok is None and action in ("create", "fill", "cancel", "collect"):
        expect_ok = True
    request_id = secrets.token_hex(12)
    body = json.dumps({"action": action, "data": data or {}, "requestId": request_id},
                      separators=(",", ":"))
    client.send(MARKET_OPCODE + string(body))
    deadline = time.monotonic() + timeout
    raw = b""
    while time.monotonic() < deadline:
        raw += client.collect(0.25)
        received = decode_market(raw)
        match = next((packet for packet in received
                      if packet.get("action") == "message"
                      and packet.get("data", {}).get("requestId") == request_id), None)
        if match:
            if expect_ok is not None and bool(match.get("data", {}).get("ok")) != expect_ok:
                raise RuntimeError(f"Market {action} rejected: {match.get('data', {}).get('text', 'no receipt')}")
            return match
        if action == "catalog" and any(packet.get("action") == "catalog" for packet in received):
            return next(packet for packet in received if packet.get("action") == "catalog")
        if action == "browse" and any(packet.get("action") == "offers" for packet in received):
            return next(packet for packet in received if packet.get("action") == "offers")
    raise TimeoutError(f"no Market response for {action}")


def parallel_calls(calls, workers=20):
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(function, *args) for function, args in calls]
        for future in as_completed(futures, timeout=25):
            results.append(future.result())
    return results


def monitor_online(online_ids, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        online = int(sql(f"SELECT COUNT(*) FROM players_online WHERE player_id IN ({online_ids})"))
        if any(client.keepalive_error for client in clients):
            raise RuntimeError("a synthetic session lost its keepalive connection")
        if online != PLAYER_COUNT:
            raise RuntimeError(f"sessions dropped during load: {online}/{PLAYER_COUNT}")
        for client in clients:
            if client.record["role"] == "chat":
                client.send(b"\x96\x01" + string("load test heartbeat"))
            elif client.record["role"] == "walker":
                client.send(b"\x65")
                client.send(b"\x67")
            client.collect(0.01)
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    print(f"online_monitor=pass expected={PLAYER_COUNT} seconds={seconds}", flush=True)


def run_smoke():
    cleanup_test_rows()
    record = seed_player(0, "hunter")
    client = StageClient(record["account"], record["password"], record["name"])
    clients.append(client)
    assert int(sql(f"SELECT COUNT(*) FROM players_online WHERE player_id={record['player']}")) == 1, (
        "welcome received but player not registered inside world; check allowClones=false"
    )
    target = find_hunt_target(client.initial)
    print(f"smoke_login=pass; map_bytes={len(client.initial)}; hunt_target={target}", flush=True)
    if target:
        client.send(b"\xa0\x02\x00\x00")
        client.send(b"\xa1" + struct.pack("<I", target[0]))
        time.sleep(5)
        print(f"smoke_attack=sent; target={target[1]}; creature_id={target[0]}", flush=True)
    client.close()
    clients.clear()
    time.sleep(2)
    wait_for_logout(matching_player_ids())
    cleanup_test_rows()


def run_load():
    cleanup_test_rows()
    group = PLAYER_COUNT // 5
    roles = (["hunter"] * group + ["seller"] * group + ["buyer"] * group
             + ["chat"] * group + ["walker"] * group)
    records = [seed_player(i, roles[i]) for i in range(PLAYER_COUNT)]
    started = time.monotonic()
    login_batch_size = 5 if PLAYER_COUNT == 10 else 10
    def login(record):
        client = StageClient(record["account"], record["password"], record["name"])
        client.record = record
        clients.append(client)  # Track successes even if another future fails.
        thread = threading.Thread(target=client.keepalive, args=(stop,), daemon=True)
        keepalive_threads.append(thread)
        thread.start()
        return client

    for batch_start in range(0, PLAYER_COUNT, login_batch_size):
        batch = records[batch_start:batch_start + login_batch_size]
        with ThreadPoolExecutor(max_workers=login_batch_size) as pool:
            futures = [pool.submit(login, record) for record in batch]
            for future in as_completed(futures, timeout=30):
                future.result()
        print(f"login_ramp={min(batch_start + login_batch_size, PLAYER_COUNT)}/{PLAYER_COUNT}", flush=True)
        time.sleep(1)

    by_index = {client.record["index"]: client for client in clients}
    online_ids = ",".join(str(record["player"]) for record in records)
    online_deadline = time.monotonic() + 5
    online_count = int(sql(f"SELECT COUNT(*) FROM players_online WHERE player_id IN ({online_ids})"))
    while online_count < PLAYER_COUNT and time.monotonic() < online_deadline:
        time.sleep(0.25)
        online_count = int(sql(f"SELECT COUNT(*) FROM players_online WHERE player_id IN ({online_ids})"))
    online_names = sql(
        f"SELECT p.name FROM players_online po JOIN players p ON p.id=po.player_id "
        f"WHERE p.account_id BETWEEN {ACCOUNT_BASE} AND {ACCOUNT_END} ORDER BY p.name"
    )
    print(f"authenticated_sessions={len(clients)}/{PLAYER_COUNT}; "
          f"online_registry={online_count}/{PLAYER_COUNT}; registry_names={online_names!r}", flush=True)
    if len(clients) != PLAYER_COUNT or online_count != PLAYER_COUNT:
        raise RuntimeError(f"expected {PLAYER_COUNT} players inside world; sessions={len(clients)}, online={online_count}; check allowClones=false")
    if len({client.creature_id for client in clients}) != PLAYER_COUNT:
        raise RuntimeError("duplicate creature IDs in login responses")

    hunt_calls = []
    hunt_targets = {}
    for index in range(group):
        client = by_index[index]
        target = find_hunt_target(client.initial)
        if target:
            hunt_targets[index] = target
            hunt_calls.append((lambda c, tid: (c.send(b"\xa0\x02\x00\x00"), c.send(b"\xa1" + struct.pack("<I", tid))),
                               (client, target[0])))
    if hunt_calls:
        parallel_calls(hunt_calls, workers=10)

    # NPC/world chat and movement traffic from real game-protocol sessions.
    chat_calls = []
    for index in range(3 * group, 4 * group):
        chat_calls.append((lambda c, text: (c.send(b"\x96\x01" + string(text)), c.collect(0.15)),
                           (by_index[index], f"load test {index:02d}")))
    parallel_calls(chat_calls, workers=10)
    for index in range(4 * group, 5 * group):
        client = by_index[index]
        client.send(b"\x65")
        client.send(b"\x67")

    # Exercise both Market currencies with inventory escrow and bank funding.
    catalog_calls = [
        (lambda client, index: (index, market_request(
            client, "catalog", {"category": "all", "search": "fish", "ownedOnly": True, "page": 1}
        )), (by_index[index], index))
        for index in range(group, 3 * group)
    ]
    for index, packet in parallel_calls(catalog_calls, workers=10):
        items = packet.get("data", {}).get("items", [])
        print(f"market_inventory_player={index} owned={[(item.get('id'), item.get('owned')) for item in items]}", flush=True)
        if group <= index < 2 * group:
            assert any(item.get("id") == 3578 and item.get("owned", 0) >= 2 for item in items), (
                "seller inventory missing two fish; verify server item IDs and container SIDs"
            )

    if NETWORK_ONLY:
        if online_count != PLAYER_COUNT:
            raise RuntimeError(f"online registry only has {online_count}/{PLAYER_COUNT} test players")
        hold_seconds = max(30, 60 - int(time.monotonic() - started))
        print(f"network_only_hold={hold_seconds}s; sessions={PLAYER_COUNT}; "
              f"catalog_queries={len(catalog_calls)}; hunt_targets={len(hunt_targets)}/{group}; "
              "market_transactions=not_run", flush=True)
        monitor_online(online_ids, hold_seconds)
        stop.set()
        for thread in keepalive_threads:
            thread.join(timeout=1)
        for client in clients:
            client.close()
        clients.clear()
        time.sleep(2)
        wait_for_logout([record["player"] for record in records])
        remaining_online = int(sql(f"SELECT COUNT(*) FROM players_online WHERE player_id IN ({online_ids})"))
        if remaining_online:
            raise RuntimeError(f"{remaining_online} synthetic sessions did not log out cleanly; test rows preserved")
        cleanup_test_rows()
        elapsed = round(time.monotonic() - started, 1)
        print(f"RESULT sessions={PLAYER_COUNT}/{PLAYER_COUNT} catalog_queries={len(catalog_calls)} "
              f"hunt_targets={len(hunt_targets)}/{group} duration_seconds={elapsed} cleanup=complete "
              "market_transactions=not_run", flush=True)
        return

    sellers = [by_index[index] for index in range(group, 2 * group)]
    buyers = [by_index[index] for index in range(2 * group, 3 * group)]
    currencies = [3031 if index < max(1, group // 2) else 5130 for index in range(group)]
    create_calls = []
    for index, buyer in enumerate(buyers):
        create_calls.append((lambda client, data, label: (label, market_request(client, "create", data)), (buyer, {
            "side": "buy", "itemId": 3578, "subtype": -1, "amount": 1,
            "price": 1, "currency": currencies[index],
        }, f"buyer-{index}")))
    for index, seller in enumerate(sellers):
        create_calls.append((lambda client, data, label: (label, market_request(client, "create", data)), (seller, {
            "side": "sell", "itemId": 3578, "subtype": -1, "amount": 1,
            "price": 1, "currency": currencies[index],
        }, f"seller-{index}")))
    create_results = parallel_calls(create_calls, workers=20)
    for label, result in create_results:
        receipt = result.get("data", {})
        print(f"market_create_player={label} ok={receipt.get('ok')} text={receipt.get('text', '')}", flush=True)

    player_to_index = {record["player"]: record["index"] for record in records}
    offer_rows = sql(
        "SELECT id,owner_guid,side,currency_id FROM market_offers "
        f"WHERE owner_guid IN ({online_ids}) AND status=1 ORDER BY id"
    )
    print(f"active_offer_rows={offer_rows!r}", flush=True)
    offers = {}
    for line in offer_rows.splitlines():
        offer_id, owner, side, currency = map(int, line.split("\t"))
        offers[(player_to_index[owner], side)] = (offer_id, currency)
    if len(offers) != 2 * group:
        raise RuntimeError(f"expected {2 * group} active test offers, found {len(offers)}")

    fill_calls = []
    for index in range(group):
        seller_index, buyer_index = group + index, 2 * group + index
        buy_offer = offers[(buyer_index, 1)][0]
        sell_offer = offers[(seller_index, 0)][0]
        fill_calls.append((market_request, (by_index[seller_index], "fill", {"offerId": buy_offer, "amount": 1})))
        fill_calls.append((market_request, (by_index[buyer_index], "fill", {"offerId": sell_offer, "amount": 1})))
    parallel_calls(fill_calls, workers=20)

    collect_calls = [(market_request, (client, "collect", {})) for client in sellers + buyers]
    parallel_calls(collect_calls, workers=20)

    history_count = int(sql(f"SELECT COUNT(*) FROM market_history WHERE player_guid IN ({online_ids})"))
    claims_count = int(sql(f"SELECT COUNT(*) FROM market_claims WHERE player_guid IN ({online_ids})"))
    active_offers = int(sql(f"SELECT COUNT(*) FROM market_offers WHERE owner_guid IN ({online_ids}) AND status=1"))
    if history_count != 4 * group or claims_count != 0 or active_offers != 0:
        raise RuntimeError(f"Market invariant failed: history={history_count}, claims={claims_count}, active={active_offers}")

    hold_seconds = max(30, 60 - int(time.monotonic() - started))
    print(f"holding_all_{PLAYER_COUNT}_seconds={hold_seconds}; hunt_targets={len(hunt_targets)}/{group}; "
          f"market_fills={2 * group}; market_currencies=gold+antigas", flush=True)
    monitor_online(online_ids, hold_seconds)
    stop.set()
    for thread in keepalive_threads:
        thread.join(timeout=1)
    if MAINTENANCE_WINDOW:
        assert run(["systemctl", "show", "imperium772", "-p", "ActiveState", "--value"]) == "inactive"
        subprocess.run(["systemctl", "stop", "imperium772-staging"], check=True, timeout=50)
        print("logout_mode=graceful_staging_stop_with_connected_clients", flush=True)
    for client in clients:
        client.close()
    clients.clear()
    time.sleep(2)
    wait_for_logout([record["player"] for record in records])
    remaining_online = int(sql(f"SELECT COUNT(*) FROM players_online WHERE player_id IN ({online_ids})"))
    if remaining_online:
        raise RuntimeError(f"{remaining_online} synthetic sessions did not log out cleanly; test rows preserved")

    # Hunters may have killed rats; storage is persisted when each player logs out.
    key_hash = 5381
    for byte in b"rat":
        key_hash = (key_hash * 33 + byte) % 600000000
    rat_key = 1500000000 + key_hash
    hunt_player_ids = ",".join(str(records[i]["player"]) for i in range(group))
    hunt_kills = int(sql(
        f"SELECT COUNT(*) FROM player_storage WHERE player_id IN "
        f"({hunt_player_ids}) AND `key`={rat_key} AND `value`>0"
    ))
    cleanup_test_rows()
    elapsed = round(time.monotonic() - started, 1)
    print(
        f"RESULT sessions={PLAYER_COUNT}/{PLAYER_COUNT} market_create={2 * group} "
        f"market_fill={2 * group} market_history={history_count} "
        f"market_pending_claims={claims_count} hunt_targets={len(hunt_targets)}/{group} "
        f"hunters_with_recorded_rat_kill={hunt_kills}/{group} duration_seconds={elapsed} cleanup=complete",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="one login + hunt-target discovery, then cleanup")
    parser.add_argument("--players", type=int, choices=(10, 50), default=50,
                        help="number of concurrent synthetic players (10 or 50)")
    parser.add_argument("--network-only", action="store_true",
                        help="hold authenticated sessions and exercise chat, movement, and catalog read paths")
    parser.add_argument("--maintenance-window", action="store_true",
                        help="require production to be stopped for the isolated staging load")
    args = parser.parse_args()
    global PLAYER_COUNT, NETWORK_ONLY, MAINTENANCE_WINDOW, DB, PORT, RSA_PUBLIC
    DB, PORT = require_staging_target()
    RSA_PUBLIC = Path(os.environ.get('ANTIGAS_RSA_PUBLIC', str(RSA_PUBLIC)))
    PLAYER_COUNT = args.players
    NETWORK_ONLY = args.network_only
    MAINTENANCE_WINDOW = args.maintenance_window
    if NETWORK_ONLY and PLAYER_COUNT != 10:
        parser.error("--network-only is limited to --players 10")
    assert_isolated_staging(require_production_active=not args.maintenance_window)
    if not RSA_PUBLIC.is_file():
        raise FileNotFoundError(f"required public RSA key is missing: {RSA_PUBLIC}")
    try:
        if args.smoke:
            run_smoke()
        else:
            run_load()
    except BaseException:
        stop.set()
        for thread in keepalive_threads:
            thread.join(timeout=1)
        for client in clients:
            client.close()
        clients.clear()
        time.sleep(2)
        try:
            wait_for_logout(matching_player_ids())
            cleanup_test_rows()
        except Exception as cleanup_error:
            print(f"cleanup_warning={cleanup_error}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
