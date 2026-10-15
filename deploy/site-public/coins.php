<?php
declare(strict_types=1);

$lib = getenv('ANTIGAS_WEB_LIB') ?: '/opt/antigas-web/private';
require $lib . '/security.php';
require $lib . '/pix.php';
webStart();
header('Cache-Control: private, no-store, max-age=0');
header('Pragma: no-cache');
header('Expires: 0');

require __DIR__ . '/i18n.php';
$language = siteStartI18n();

function e($value): string
{
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function brl(int $cents): string
{
    return 'R$ ' . number_format($cents / 100, 2, ',', '.');
}

$coinPackages = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000];
$account = null;
$characters = [];
$orders = [];
$selected = null;
$quote = null;
$message = '';

try {
    $database = webDb();
    $account = webAccount($database);
    if (!$account) {
        if (isset($_GET['qr'])) {
            http_response_code(401);
            exit;
        }
    } else {
        $statement = $database->prepare('SELECT id,name FROM players WHERE account_id=? AND deleted=0 ORDER BY name');
        $statement->execute([(int)$account['id']]);
        $characters = $statement->fetchAll(PDO::FETCH_ASSOC);

        if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
            if (!isset($_SESSION['csrf']) || !is_string($_SESSION['csrf'])
                || !hash_equals($_SESSION['csrf'], webField('csrf', 64))) {
                http_response_code(403);
                throw new DomainException(siteTranslation('Your form has expired. Refresh the page.'));
            }

            $nonce = webField('nonce', 32);
            $sessionNonce = $_SESSION['coin_order_nonce'] ?? '';
            if (!is_string($sessionNonce) || !preg_match('/\A[a-f0-9]{32}\z/D', $nonce)
                || !hash_equals($sessionNonce, $nonce)) {
                http_response_code(403);
                throw new DomainException(siteTranslation('Your form has expired. Refresh the page.'));
            }
            unset($_SESSION['coin_order_nonce']);

            if (!webLimit('pix:' . (int)$account['id'], 20, 3600)
                || !webLimit('pix-ip:' . (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown'), 40, 3600)) {
                http_response_code(429);
                throw new DomainException(siteTranslation('Too many attempts. Wait one hour.'));
            }

            $amountText = webField('coins', 5);
            if (!in_array($amountText, array_map('strval', $coinPackages), true)) {
                http_response_code(400);
                throw new DomainException(siteTranslation('Invalid amount or character.'));
            }

            $characterText = webField('character', 10);
            if (!ctype_digit($characterText) || (int)$characterText < 1) {
                http_response_code(400);
                throw new DomainException(siteTranslation('Invalid amount or character.'));
            }
            $characterId = (int)$characterText;
            $statement = $database->prepare('SELECT id FROM players WHERE id=? AND account_id=? AND deleted=0');
            $statement->execute([$characterId, (int)$account['id']]);
            if (!$statement->fetch(PDO::FETCH_ASSOC)) {
                http_response_code(400);
                throw new DomainException(siteTranslation('Invalid amount or character.'));
            }

            $quote = pixQuote();
            $orderId = pixOrder($database, (int)$account['id'], $characterId, (int)$amountText, $nonce, $quote);
            if (!preg_match('/\A[a-f0-9]{32}\z/D', $orderId)) {
                throw new RuntimeException('Payment helper returned an invalid order identifier.');
            }
            header('Location: /coins.php?order=' . rawurlencode($orderId), true, 303);
            exit;
        }

        $orderId = $_GET['order'] ?? null;
        if ($orderId !== null) {
            if (!is_string($orderId) || !preg_match('/\A[a-f0-9]{32}\z/D', $orderId)) {
                http_response_code(404);
                throw new DomainException(siteTranslation('Order not found.'));
            }
            $statement = $database->prepare('SELECT o.*,p.name FROM coin_orders o LEFT JOIN players p ON p.id=o.character_id WHERE public_id=? AND o.account_id=?');
            $statement->execute([$orderId, (int)$account['id']]);
            $selected = $statement->fetch(PDO::FETCH_ASSOC);
            if (!$selected) {
                http_response_code(404);
                throw new DomainException(siteTranslation('Order not found.'));
            }

            if (isset($_GET['qr'])) {
                if (($selected['status'] ?? '') !== 'pending') {
                    http_response_code(410);
                    exit;
                }
                $png = pixQr((string)$selected['payload']);
                header('Content-Type: image/png');
                header('Content-Length: ' . strlen($png));
                echo $png;
                exit;
            }
        }

        if (!$selected) {
            $statement = $database->prepare('SELECT public_id,coins,brl_cents,status,created_at FROM coin_orders WHERE account_id=? ORDER BY id DESC LIMIT 20');
            $statement->execute([(int)$account['id']]);
            $orders = $statement->fetchAll(PDO::FETCH_ASSOC);

            try {
                $quote = pixQuote();
            } catch (DomainException $exception) {
                $message = $language === 'pt' ? $exception->getMessage()
                    : siteTranslation('The pricing service is temporarily unavailable. Please try again later.');
            }
        }

        if (!$selected && !isset($_SESSION['coin_order_nonce'])) {
            $_SESSION['coin_order_nonce'] = bin2hex(random_bytes(16));
        }
    }
} catch (DomainException $exception) {
    if ($message === '') $message = $exception->getMessage();
} catch (Throwable $exception) {
    error_log('Antigas coin service unavailable: ' . get_class($exception) . ' code ' . $exception->getCode());
    http_response_code(503);
    $message = siteTranslation('The coin service is temporarily unavailable.');
}
?>
<!doctype html>
<html lang="<?= e(siteLanguageTag()) ?>">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= siteT('Antigas Coins — Tibia 7.4') ?></title>
    <link rel="stylesheet" href="/classic-2004.css?v=20260924-1">
    <link rel="stylesheet" href="/coins.css">
    <link rel="stylesheet" href="/language.css?v=security-20260928">
    <link rel="stylesheet" href="/classic-refinement.css?v=classic-20261003-1">
</head>
<body class="coins-page">
<a class="skip-link" href="#conteudo"><?= siteT('Skip to content') ?></a>
<div class="skyline">
    <header class="masthead">
        <a class="wordmark" href="/"><span>Antigas</span><i>7.4 CLASSIC</i></a>
        <p class="motto"><?= siteT('Your next adventure starts here.') ?></p>
    </header>
    <nav class="topnav" aria-label="<?= siteT('Main navigation') ?>">
        <a href="/"><?= siteT('Home') ?></a>
        <a href="/account.php"><?= siteT('My account') ?></a>
        <a href="/coins.php" aria-current="page"><?= siteT('Antigas Coins') ?></a>
        <a href="/#download"><?= siteT('Download') ?></a>
    </nav>
    <?= siteLanguageSwitcher() ?>
</div>
<div class="layout">
    <aside class="sidebar">
        <nav class="stone-menu">
            <h2>Tibia 7.4</h2>
            <a href="/"><?= siteT('Return home') ?></a>
            <a href="/account.php"><?= siteT('My account') ?></a>
            <a href="/#market"><?= siteT('Learn about the Market') ?></a>
        </nav>
        <p class="side-signature">Antigas<span>7.4</span></p>
    </aside>
    <main class="paper" id="conteudo" tabindex="-1">
        <section class="page-title">
            <h1><?= siteT('Antigas Coins') ?></h1>
            <p><?= siteT('Pix in BRL · Manual approval · Delivered through the Market') ?></p>
        </section>
        <p class="coin-intro"><?= siteT('10 Antigas Coins = US$ 1. The BRL price uses the latest available PTAX sell rate and is fixed when you place an order.') ?></p>
        <?php if ($message !== ''): ?>
            <div class="notice error" role="status"><?= e($message) ?></div>
        <?php endif; ?>

        <?php if (!$account): ?>
            <section class="coin-panel">
                <h2><?= siteT('Sign in to buy') ?></h2>
                <p><?= siteT('The order is linked to your account and selected character.') ?></p>
                <a class="button primary" href="/account.php"><?= siteT('Sign in to your account') ?></a>
            </section>
        <?php elseif ($selected): ?>
            <section class="coin-panel">
                <h2><?= siteT('Order · {coins} coins', ['coins' => e($selected['coins'])]) ?></h2>
                <dl class="order-details">
                    <div><dt><?= siteT('Character') ?></dt><dd><?= e($selected['name'] ?? $selected['character_id']) ?></dd></div>
                    <div><dt><?= siteT('Fixed total') ?></dt><dd class="coin-price"><?= brl((int)$selected['brl_cents']) ?></dd></div>
                    <div><dt><?= siteT('Exchange rate used') ?></dt><dd>US$ 1 = R$ <?= number_format((int)$selected['rate4'] / 10000, 4, ',', '.') ?> · PTAX <?= e($selected['rate_date']) ?></dd></div>
                </dl>
                <?php if (($selected['status'] ?? '') === 'approved'): ?>
                    <div class="notice success"><?= siteT('Payment approved. Log into the game with the selected character and click Market → Collect depot to receive the coins in its hometown depot.') ?></div>
                <?php elseif (($selected['status'] ?? '') === 'pending'): ?>
                    <div class="pix-grid">
                        <div>
                            <img class="pix-qr" src="/coins.php?order=<?= e($selected['public_id']) ?>&amp;qr=1" alt="<?= siteT('Pix QR code for this order, amount {amount}', ['amount' => brl((int)$selected['brl_cents'])]) ?>">
                            <p class="small-note"><?= siteT('Pay only once. Delivery is not instant.') ?></p>
                        </div>
                        <div>
                            <h3><?= siteT('Payment details') ?></h3>
                            <p><?= siteT('Check the recipient name and amount in your banking app before confirming.') ?></p>
                            <label for="pix-code"><?= siteT('Pix copy-and-paste code') ?></label>
                            <textarea id="pix-code" readonly rows="5"><?= e($selected['payload']) ?></textarea>
                            <p class="small-note"><?= siteT('Select and copy the code above. Wait for the manual statement check. Generating this QR code does not confirm payment.') ?></p>
                        </div>
                    </div>
                <?php else: ?>
                    <div class="notice error"><?= siteT('This order is no longer awaiting payment.') ?></div>
                <?php endif; ?>
                <p class="small-note">
                    <?= siteT('Reference:') ?> <?= e($selected['txid']) ?><br>
                    <?= siteT('Order:') ?> <?= e($selected['public_id']) ?>.
                    <?= siteT('Keep your receipt and order number. If you have already paid, do not pay again; wait for confirmation.') ?>
                </p>
                <a href="/coins.php"><?= siteT('Back to my orders') ?></a>
            </section>
        <?php endif; ?>

        <?php if ($account && !$selected && $quote): ?>
            <section class="coin-panel">
                <h2><?= siteT('Create order') ?></h2>
                <p><?= siteT('PTAX sell rate for {date}: US$ 1 = R$ {rate}. Updated automatically; this is not a real-time quote.', [
                    'date' => e($quote['date']),
                    'rate' => number_format((int)$quote['rate4'] / 10000, 4, ',', '.'),
                ]) ?></p>
                <form method="post" action="/coins.php">
                    <input type="hidden" name="csrf" value="<?= e($_SESSION['csrf']) ?>">
                    <input type="hidden" name="nonce" value="<?= e($_SESSION['coin_order_nonce']) ?>">
                    <label for="character"><?= siteT('Character to receive the coins') ?></label>
                    <select id="character" name="character" required>
                        <?php foreach ($characters as $character): ?>
                            <option value="<?= (int)$character['id'] ?>"><?= e($character['name']) ?></option>
                        <?php endforeach; ?>
                    </select>
                    <label for="coins"><?= siteT('Amount of coins') ?></label>
                    <select id="coins" name="coins" required>
                        <?php foreach ($coinPackages as $amount): ?>
                            <?php $brlCents = intdiv($amount * 10 * (int)$quote['rate4'] + 5000, 10000); ?>
                            <option value="<?= $amount ?>"><?= number_format($amount, 0, ',', '.') ?> coins — <?= brl($brlCents) ?></option>
                        <?php endforeach; ?>
                    </select>
                    <button class="button primary"<?= !$characters ? ' disabled' : '' ?>><?= siteT('Generate order and QR code') ?></button>
                    <p class="small-note"><?= siteT('Creating an order does not charge your bank account. The final amount appears in the QR code. Coins are in-game items and are separate from Shop points.') ?></p>
                </form>
            </section>
        <?php endif; ?>

        <?php if ($account && $orders && !$selected): ?>
            <section class="coin-panel">
                <h2><?= siteT('My orders') ?></h2>
                <div class="orders">
                    <?php foreach ($orders as $order): ?>
                        <a href="/coins.php?order=<?= e($order['public_id']) ?>">
                            <strong><?= number_format((int)$order['coins'], 0, ',', '.') ?> coins · <?= brl((int)$order['brl_cents']) ?></strong>
                            <span><?= siteT(match ($order['status'] ?? '') {
                                'approved' => 'Approved · collect in the Market',
                                'pending' => 'Awaiting manual review',
                                default => 'Order closed · contact support',
                            }) ?></span>
                            <small><?= e($order['created_at']) ?> UTC</small>
                        </a>
                    <?php endforeach; ?>
                </div>
            </section>
        <?php endif; ?>

        <section class="coin-panel">
            <h2><?= siteT('How delivery works') ?></h2>
            <ol>
                <li><?= siteT('Choose your character and create the order.') ?></li>
                <li><?= siteT('Pay the exact Pix amount and check the recipient.') ?></li>
                <li><?= siteT('Wait for manual approval by Tibia 7.4.') ?></li>
                <li><?= siteT('In the game, open the Market and click Collect depot. Coins go to your hometown depot. If it is full, make room and try again.') ?></li>
            </ol>
            <p><?= siteT('Never share your password. A player-submitted receipt never releases coins automatically.') ?></p>
        </section>
        <footer><?= siteT('Tibia 7.4 · Antigas 7.4 · Independent community project.') ?></footer>
    </main>
</div>
</body>
</html>
