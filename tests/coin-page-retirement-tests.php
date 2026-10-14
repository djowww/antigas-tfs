<?php
declare(strict_types=1);

$route = $argv[1] ?? 'GET';
if (!in_array($route, ['GET', 'POST', 'QR'], true)) {
    throw new RuntimeException('Unknown test route');
}
$temp = sys_get_temp_dir() . '/antigas-coins-retirement-' . bin2hex(random_bytes(8));
if (!mkdir($temp, 0700)) {
    throw new RuntimeException('Could not create isolated provider fixture');
}
register_shutdown_function(static function () use ($temp): void {
    foreach (['security.php', 'pix.php'] as $file) {
        if (is_file($temp . '/' . $file)) unlink($temp . '/' . $file);
    }
    rmdir($temp);
});
$GLOBALS['retirementCalls'] = ['webStart' => 0, 'webDb' => 0, 'pixOrder' => 0, 'pixQr' => 0, 'pixQuote' => 0];
file_put_contents($temp . '/security.php', <<<'PHP'
<?php
function webStart(): void { $GLOBALS['retirementCalls']['webStart']++; $_SESSION=['csrf'=>'fixture']; }
function webDb() { $GLOBALS['retirementCalls']['webDb']++; throw new RuntimeException('Database access forbidden on retired page'); }
PHP);
file_put_contents($temp . '/pix.php', <<<'PHP'
<?php
function pixOrder(...$args) { $GLOBALS['retirementCalls']['pixOrder']++; throw new RuntimeException('No orders allowed'); }
function pixQr(...$args) { $GLOBALS['retirementCalls']['pixQr']++; throw new RuntimeException('No QR allowed'); }
function pixQuote(...$args) { $GLOBALS['retirementCalls']['pixQuote']++; throw new RuntimeException('No quote allowed'); }
PHP);
putenv('ANTIGAS_WEB_LIB=' . $temp);
$_SERVER['REQUEST_METHOD'] = $route === 'POST' ? 'POST' : 'GET';
$_SERVER['REQUEST_URI'] = '/coins.php';
$_GET = $route === 'QR' ? ['qr' => '1', 'order' => str_repeat('a', 32)] : [];
$_POST = $route === 'POST' ? ['coins' => '100', 'character' => '1', 'csrf' => 'fixture', 'nonce' => str_repeat('b', 32)] : [];
ob_start();
require __DIR__ . '/../deploy/site-public/coins.php';
$body = ob_get_clean();
if (http_response_code() !== 410) {
    throw new RuntimeException($route . ' expected HTTP 410, got ' . http_response_code());
}
if ($GLOBALS['retirementCalls'] !== ['webStart' => 1, 'webDb' => 0, 'pixOrder' => 0, 'pixQr' => 0, 'pixQuote' => 0]) {
    throw new RuntimeException('Retired page reached a provider: ' . json_encode($GLOBALS['retirementCalls']));
}
if (strpos($body, 'Antigas Coins are unavailable. This item was retired from the test environment.') === false) {
    throw new RuntimeException('Withdrawal notice missing');
}
foreach (['<form', 'pix-code', 'pix-qr', 'Generate order', 'Copy and paste'] as $control) {
    if (strpos($body, $control) !== false) throw new RuntimeException('Payment control remains: ' . $control);
}
echo 'PASS ' . $route . ': HTTP410, webStart once, zero database/order/quote/QR calls, no payment controls' . PHP_EOL;
