<?php
declare(strict_types=1);

// This public distribution does not publish payment recipient information.
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: private, no-store, max-age=0');
header('Pragma: no-cache');
header('Expires: 0');
header('X-Content-Type-Options: nosniff');
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET' || isset($_GET['order']) || isset($_GET['qr'])) {
    http_response_code(410);
}
?>
<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Tibia 7.4 — Comunidade</title><link rel="stylesheet" href="/blog.css?v=20261023-2"></head>
<body><main class="page"><p class="eyebrow">TIBIA 7.4 · A CLASSIC RPG VERSION</p><h1>Projeto da comunidade</h1><p>Compras pelo site estão desativadas. O jogo e as trocas entre jogadores continuam disponíveis.</p><p><a href="/">Voltar ao diário e aos downloads →</a></p></main></body></html>
