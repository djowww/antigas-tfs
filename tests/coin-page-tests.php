<?php
declare(strict_types=1);

const COIN_PACKAGES = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000];
const COIN_ORDER_ID = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

function coinCase(): string
{
    return $GLOBALS['coinCase'] ?? '';
}

function coinFixtureRows(string $query, array $params): array
{
    $GLOBALS['queryLog'][] = [$query, $params];
    if (str_contains($query, 'FROM players') && !str_contains($query, 'LEFT JOIN')) {
        if (str_contains($query, 'SELECT id,name FROM players')) {
            return [['id' => 17, 'name' => 'Fixture Knight']];
        }
        return isset($params[0], $params[1]) && (int)$params[0] === 17 && (int)$params[1] === 1
            ? [['id' => 17]] : [];
    }
    if (str_contains($query, 'FROM coin_orders o LEFT JOIN players')) {
        $id = $params[0] ?? '';
        $account = (int)($params[1] ?? 0);
        $case = coinCase();
        if ($case === 'foreign-order-qr') return [];
        $expectedId = $case === 'approved-order-qr' ? str_repeat('b', 32) : COIN_ORDER_ID;
        if ($id !== $expectedId || $account !== 1) {
            return [];
        }
        return [[
            'public_id' => $expectedId,
            'account_id' => 1,
            'character_id' => 17,
            'name' => 'Fixture Knight',
            'coins' => 100,
            'usd_cents' => 1000,
            'rate4' => 54321,
            'rate_date' => '2026-10-13',
            'brl_cents' => 5432,
            'payload' => 'FIXTURE-PIX-COPY-CODE',
            'txid' => 'TEST-REFERENCE',
            'status' => match ($case) {
                'approved-order-qr' => 'approved',
                'closed-order' => 'rejected',
                default => 'pending',
            },
            'created_at' => '2026-10-14 12:00:00',
        ]];
    }
    if (str_contains($query, 'FROM coin_orders WHERE account_id')) {
        return [];
    }
    throw new RuntimeException('Unexpected fixture SQL: ' . $query);
}

final class CoinFixturePDO extends PDO
{
    public function __construct() {}

    public function prepare(string $query, array $options = []): PDOStatement|false
    {
        return new CoinFixturePDOStatement($query);
    }
}

final class CoinFixturePDOStatement extends PDOStatement
{
    private array $rows = [];
    private int $cursor = 0;

    public function __construct(private readonly string $query) {}

    public function execute(?array $params = null): bool
    {
        $this->rows = coinFixtureRows($this->query, $params ?? []);
        $this->cursor = 0;
        return true;
    }

    public function fetch(int $mode = PDO::FETCH_DEFAULT, int $cursorOrientation = PDO::FETCH_ORI_NEXT, int $cursorOffset = 0): mixed
    {
        return $this->rows[$this->cursor++] ?? false;
    }

    public function fetchAll(int $mode = PDO::FETCH_DEFAULT, mixed ...$args): array
    {
        return $this->rows;
    }
}

function webStart(string $name = 'antigas_account'): void
{
    $case = coinCase();
    $_SESSION = ['csrf' => 'fixture-csrf'];
    if (str_starts_with($case, 'post-')) {
        $_SESSION['coin_order_nonce'] = $case === 'post-reused-nonce' ? 'a-different-unused-token' : str_repeat('c', 32);
    }
    $GLOBALS['webStartCalls']++;
}

function webDb(): PDO
{
    $GLOBALS['webDbCalls']++;
    return new CoinFixturePDO();
}

function webAccount(PDO $pdo): ?array
{
    return coinCase() === 'signed-out' ? null : ['id' => 1, 'name' => 'Fixture Account'];
}

function webField(string $name, int $limit = 512): string
{
    $value = $_POST[$name] ?? '';
    return is_string($value) && strlen($value) <= $limit ? $value : '';
}

function webLimit(string $key, int $limit, int $seconds = 900): bool
{
    $GLOBALS['limitCalls'][] = $key;
    if (coinCase() === 'post-account-limit' && str_starts_with($key, 'pix:')) return false;
    if (coinCase() === 'post-ip-limit' && str_starts_with($key, 'pix-ip:')) return false;
    return true;
}

function pixQuote(): array
{
    $GLOBALS['quoteCalls']++;
    if (coinCase() === 'post-stale-fetch' || coinCase() === 'post-stale-date') {
        throw new DomainException('Fixture quote is stale.');
    }
    return ['rate4' => 55000, 'date' => gmdate('Y-m-d'), 'fetched_at' => time()];
}

function pixOrder(PDO $db, int $account, int $character, int $coins, string $nonce, array $quote): string
{
    $GLOBALS['pixOrderCalls']++;
    $GLOBALS['pixOrderInput'] = compact('account', 'character', 'coins', 'nonce', 'quote');
    if ($account !== 1 || $character !== 17) {
        throw new DomainException('Choose a character that belongs to this account.');
    }
    if (!in_array($coins, COIN_PACKAGES, true)) {
        throw new DomainException('Invalid package.');
    }
    return str_repeat('d', 32);
}

function pixQr(string $payload): string
{
    $GLOBALS['pixQrCalls']++;
    if ($payload !== 'FIXTURE-PIX-COPY-CODE') throw new RuntimeException('Unexpected QR payload.');
    return 'FIXTURE-PNG-BYTES';
}

function coinChild(string $case): never
{
    $GLOBALS['coinCase'] = $case;
    $GLOBALS['webStartCalls'] = 0;
    $GLOBALS['webDbCalls'] = 0;
    $GLOBALS['pixOrderCalls'] = 0;
    $GLOBALS['pixOrderInput'] = null;
    $GLOBALS['pixQrCalls'] = 0;
    $GLOBALS['quoteCalls'] = 0;
    $GLOBALS['limitCalls'] = [];
    $GLOBALS['queryLog'] = [];

    $isPost = str_starts_with($case, 'post-');
    $_SERVER['REQUEST_METHOD'] = $isPost ? 'POST' : 'GET';
    $_SERVER['REQUEST_URI'] = '/coins.php';
    $_SERVER['REMOTE_ADDR'] = '192.0.2.10';
    $_GET = [];
    $_POST = [];
    if ($isPost) {
        $amount = substr($case, 5);
        if (in_array($case, ['post-foreign-character', 'post-invalid-csrf', 'post-reused-nonce', 'post-account-limit', 'post-ip-limit', 'post-stale-fetch', 'post-stale-date'], true)) {
            $amount = '100';
        }
        $_POST = [
            'coins' => $amount === 'valid' ? '100' : $amount,
            'character' => $case === 'post-foreign-character' ? '99' : '17',
            'csrf' => $case === 'post-invalid-csrf' ? 'wrong-token' : 'fixture-csrf',
            'nonce' => str_repeat('c', 32),
        ];
    } elseif (in_array($case, ['pending-order', 'same-account-qr', 'foreign-order-qr', 'approved-order-qr', 'frozen-order', 'closed-order'], true)) {
        $id = $case === 'foreign-order-qr' ? str_repeat('f', 32)
            : ($case === 'approved-order-qr' ? str_repeat('b', 32)
                : ($case === 'closed-order' ? str_repeat('e', 32) : COIN_ORDER_ID));
        $_GET['order'] = $id;
        if ($case === 'same-account-qr' || $case === 'foreign-order-qr' || $case === 'approved-order-qr') $_GET['qr'] = '1';
    }

    $temp = sys_get_temp_dir() . '/antigas-coin-fixture-' . bin2hex(random_bytes(8));
    if (!mkdir($temp, 0700)) throw new RuntimeException('Could not create isolated helper fixture.');
    file_put_contents($temp . '/security.php', "<?php\n");
    file_put_contents($temp . '/pix.php', "<?php\n");
    putenv('ANTIGAS_WEB_LIB=' . $temp);
    register_shutdown_function(static function () use ($temp): void {
        $body = ob_get_level() > 0 ? (string)ob_get_contents() : '';
        while (ob_get_level() > 0) ob_end_clean();
        echo '__COIN_RESULT__' . json_encode([
            'status' => http_response_code() ?: 200,
            'body' => $body,
            'webStartCalls' => $GLOBALS['webStartCalls'],
            'webDbCalls' => $GLOBALS['webDbCalls'],
            'pixOrderCalls' => $GLOBALS['pixOrderCalls'],
            'pixOrderInput' => $GLOBALS['pixOrderInput'],
            'pixQrCalls' => $GLOBALS['pixQrCalls'],
            'quoteCalls' => $GLOBALS['quoteCalls'],
            'limitCalls' => $GLOBALS['limitCalls'],
            'queryLog' => $GLOBALS['queryLog'],
        ], JSON_THROW_ON_ERROR) . PHP_EOL;
        @unlink($temp . '/security.php');
        @unlink($temp . '/pix.php');
        @rmdir($temp);
    });
    ob_start();
    require __DIR__ . '/../deploy/site-public/coins.php';
    exit;
}

function runCoinCase(string $case): array
{
    $command = [PHP_BINARY, 'tests/coin-page-tests.php', '--case', $case];
    $pipes = [];
    $process = proc_open($command, [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes, dirname(__DIR__));
    if (!is_resource($process)) throw new RuntimeException('Could not start isolated case: ' . $case);
    fclose($pipes[0]);
    $stdout = stream_get_contents($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    $exit = proc_close($process);
    $marker = strrpos($stdout, '__COIN_RESULT__');
    if ($marker === false) throw new RuntimeException($case . ' fixture failed (exit ' . $exit . '): ' . trim($stderr . "\n" . $stdout));
    $result = json_decode(substr($stdout, $marker + strlen('__COIN_RESULT__')), true, 512, JSON_THROW_ON_ERROR);
    $result['stderr'] = $stderr;
    return $result;
}

function expect(bool $condition, string $message): void
{
    if (!$condition) throw new RuntimeException($message);
}

if (($argv[1] ?? '') === '--case') {
    coinChild($argv[2] ?? '');
}

foreach (COIN_PACKAGES as $package) {
    $result = runCoinCase('post-' . $package);
    expect($result['status'] === 303, 'Valid package must redirect after order creation: ' . $package);
    expect($result['pixOrderCalls'] === 1, 'Valid package must create exactly one fixture order: ' . $package);
    expect($result['pixOrderInput']['coins'] === $package, 'The selected package must reach the helper unchanged: ' . $package);
    expect($result['pixOrderInput']['quote']['rate4'] === 55000, 'The helper must receive the fixed PTAX quote.');
    echo 'PASS exact package ' . $package . PHP_EOL;
}

$form = runCoinCase('form');
expect($form['status'] === 200, 'Signed-in checkout form should load.');
expect(str_contains($form['body'], '10 Antigas Coins = US$ 1.'), 'Checkout must explain the Coin/USD pricing rule.');
expect(str_contains($form['body'], 'R$ 5,50'), 'Ten Coins at the fixture PTAX rate must show the rounded BRL price.');
foreach (COIN_PACKAGES as $package) expect(str_contains($form['body'], 'value="' . $package . '"'), 'Package option is missing: ' . $package);
expect($form['pixOrderCalls'] === 0, 'Loading the form must not create an order.');
echo 'PASS signed-in form, all packages and PTAX calculation' . PHP_EOL;

$signedOut = runCoinCase('signed-out');
expect($signedOut['status'] === 200 && !str_contains($signedOut['body'], '<form'), 'Signed-out users must not receive checkout controls.');
echo 'PASS signed-out route' . PHP_EOL;

foreach (['11', '050', '10001', '0', 'abc'] as $amount) {
    $result = runCoinCase('post-' . $amount);
    expect($result['pixOrderCalls'] === 0, 'Invalid/tampered amount reached pixOrder: ' . $amount);
    expect($result['status'] === 400, 'Invalid/tampered amount should be rejected: ' . $amount);
    echo 'PASS rejects amount ' . $amount . PHP_EOL;
}

foreach (['post-foreign-character', 'post-invalid-csrf', 'post-reused-nonce', 'post-account-limit', 'post-ip-limit', 'post-stale-fetch', 'post-stale-date'] as $case) {
    $result = runCoinCase($case);
    expect($result['pixOrderCalls'] === 0, 'Rejected request reached pixOrder: ' . $case);
    if (str_contains($case, 'limit')) expect($result['status'] === 429, 'Rate-limited request should be rejected: ' . $case);
    if (str_contains($case, 'csrf') || str_contains($case, 'nonce')) expect($result['status'] === 403, 'Invalid/reused request token should be rejected: ' . $case);
    echo 'PASS rejects ' . $case . PHP_EOL;
}

$pending = runCoinCase('pending-order');
expect(str_contains($pending['body'], 'FIXTURE-PIX-COPY-CODE') && str_contains($pending['body'], 'qr=1'), 'Pending order must show QR and copy code.');
expect($pending['pixQrCalls'] === 0 && $pending['quoteCalls'] === 0, 'Order details must use stored values without regenerating QR or quote.');
echo 'PASS pending order keeps its saved quote and payment code' . PHP_EOL;

$qr = runCoinCase('same-account-qr');
expect($qr['status'] === 200 && $qr['pixQrCalls'] === 1, 'Same-account pending order must render its QR.');
expect(str_contains($qr['body'], 'FIXTURE-PNG-BYTES'), 'QR fixture response is missing.');
expect((bool)array_filter($qr['queryLog'], static fn(array $q): bool => str_contains($q[0], 'o.account_id=?') && ($q[1][1] ?? null) === 1), 'Order QR query must be scoped to the signed-in account.');
echo 'PASS account-scoped QR route' . PHP_EOL;

$foreignQr = runCoinCase('foreign-order-qr');
expect($foreignQr['status'] === 404 && $foreignQr['pixQrCalls'] === 0, 'Foreign order QR must not be disclosed.');
echo 'PASS foreign-account QR is hidden' . PHP_EOL;

$approvedQr = runCoinCase('approved-order-qr');
expect($approvedQr['status'] === 410 && $approvedQr['pixQrCalls'] === 0, 'Approved order QR must not be regenerated.');
echo 'PASS approved order QR is closed' . PHP_EOL;

$closed = runCoinCase('closed-order');
expect(!str_contains($closed['body'], 'pix-code') && !str_contains($closed['body'], 'qr=1'), 'Closed order must not show payment details.');
echo 'PASS closed order does not show payment details' . PHP_EOL;

$frozen = runCoinCase('frozen-order');
expect(str_contains($frozen['body'], 'R$ 54,32') && str_contains($frozen['body'], '5,4321'), 'Existing order must display its frozen BRL total and rate.');
expect($frozen['quoteCalls'] === 0, 'Opening an existing order must not refresh or replace its saved quote.');
echo 'PASS existing order keeps frozen quote' . PHP_EOL;
