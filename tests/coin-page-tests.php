<?php
declare(strict_types=1);

// Run each route separately: the retired endpoint may exit early.
if (($argv[1] ?? '') === '--case') {
    $_SERVER['REQUEST_METHOD'] = $argv[2];
    parse_str($argv[3] ?? '', $_GET);
    $_POST = ['coins' => '10', 'character' => '1'];
    putenv('ANTIGAS_WEB_LIB=/nonexistent/private-payment-library');
    ob_start();
    register_shutdown_function(static function (): void {
        $body = ob_get_clean();
        echo json_encode(['status' => http_response_code() ?: 200, 'body' => $body]);
    });
    require __DIR__ . '/../deploy/site-public/coins.php';
    exit;
}
$cases = [
    ['GET', '', 200],
    ['GET', 'order=' . str_repeat('a', 32), 410],
    ['GET', 'qr=1&order=' . str_repeat('a', 32), 410],
    ['GET', 'qr[]=1', 410],
    ['POST', '', 410],
    ['POST', 'qr=1', 410],
];
foreach ($cases as [$method, $query, $status]) {
    $command = escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg(__FILE__)
        . ' --case ' . escapeshellarg($method) . ' ' . escapeshellarg($query);
    exec($command, $output, $exit);
    $result = json_decode(implode("\n", $output), true);
    $output = [];
    if ($exit !== 0 || !is_array($result) || $result['status'] !== $status) {
        throw new RuntimeException('Public payment endpoint must be retired without loading private libraries: ' . $method . ' ' . $query);
    }
    if (preg_match('/pix|<form|<img|payload|payment-code|@/i', $result['body'])) {
        throw new RuntimeException('Retired endpoint exposed payment controls or recipient information.');
    }
    if (!str_contains($result['body'], 'href="/"')) {
        throw new RuntimeException('Retired endpoint must link back to the public journal.');
    }
    echo 'PASS retired public payment endpoint: ' . $method . ' ' . ($query ? 'legacy query' : 'page') . PHP_EOL;
}
