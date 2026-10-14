<?php
declare(strict_types=1);
$lib=getenv('ANTIGAS_WEB_LIB')?:'/opt/antigas-web/private';require $lib.'/security.php';webStart();
header('Cache-Control: private, no-store, max-age=0');
header('Pragma: no-cache');
header('Expires: 0');
http_response_code(410);
require __DIR__.'/i18n.php';$language=siteStartI18n();
function e($s): string {return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
?>
<!doctype html><html lang="<?= e(siteLanguageTag()) ?>"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title><?= siteT('Antigas Coins — Tibia 7.4') ?></title><link rel="stylesheet" href="/classic-2004.css?v=20260924-1"><link rel="stylesheet" href="/coins.css"><link rel="stylesheet" href="/language.css?v=security-20260928"><link rel="stylesheet" href="/classic-refinement.css?v=classic-20261003-1"></head>
<body class="coins-page"><a class="skip-link" href="#conteudo"><?= siteT('Skip to content') ?></a><div class="skyline"><header class="masthead"><a class="wordmark" href="/"><span>Antigas</span><i>7.4 CLASSIC</i></a><p class="motto"><?= siteT('Your next adventure starts here.') ?></p></header><nav class="topnav" aria-label="<?= siteT('Main navigation') ?>"><a href="/"><?= siteT('Home') ?></a><a href="/wiki.php"><?= siteT('Wiki Antigas') ?></a><a href="/account.php"><?= siteT('My account') ?></a><a href="/coins.php" aria-current="page"><?= siteT('Antigas Coins') ?></a><a href="/#download"><?= siteT('Download') ?></a></nav><?= siteLanguageSwitcher() ?></div>
<div class="layout"><aside class="sidebar"><nav class="stone-menu"><h2>Tibia 7.4</h2><a href="/"><?= siteT('Return home') ?></a><a href="/account.php"><?= siteT('My account') ?></a><a href="/#market"><?= siteT('Learn about the Market') ?></a></nav><p class="side-signature">Antigas<span>7.4</span></p></aside><main class="paper" id="conteudo" tabindex="-1">
<section class="page-title"><h1><?= siteT('Antigas Coins') ?></h1></section>
<section class="coin-panel"><div class="notice error" role="status"><?= siteT('Antigas Coins are unavailable. This item was retired from the test environment.') ?></div><a class="button primary" href="/account.php"><?= siteT('My account') ?></a></section>
<footer><?= siteT('Tibia 7.4 · Antigas 7.4 · Independent community project.') ?></footer></main></div></body></html>
