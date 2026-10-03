<?php
declare(strict_types=1);
require (getenv('ANTIGAS_WEB_LIB') ?: '/opt/antigas-web/private') . '/security.php';
webStart();
require __DIR__ . '/i18n.php';
siteStartI18n();
function e(string $value): string { return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
$sections = [
    'getting-started' => ['Getting started', 'Create an account on this site, download the configured client and start your first character in Rookgaard. Keep your account number and password private. Use Help for questions, Trade to advertise trades and World Chat for general conversation.'],
    'vocations' => ['Vocations and promotion', 'Sorcerers and Druids gain 5 health, 30 mana and 10 capacity per level. Paladins gain 10 health, 15 mana and 20 capacity. Knights gain 15 health, 5 mana and 25 capacity. Promotions are Master Sorcerer, Elder Druid, Royal Paladin and Elite Knight.'],
    'online-bonus' => ['Online bonus', 'Each full continuous hour online grants +0.2% experience and skill bonus, up to 5%. Logging out before the next full hour does not add that hour. The bonus is saved for your character.'],
    'combat-pvp' => ['Combat and PvP', 'Attack, Balanced and Defense fighting modes change your physical weapon damage and protection trade-off. Use !frags to check kill counts and !pz to check your protection-zone lock. Follow the server rules when fighting other players.'],
    'spells-runes' => ['Spells and runes', 'Use the client spell list to search by name, vocation and required level. Instant spells consume mana; runes are created by casting a rune spell while carrying the required blank rune. Check your vocation and level before hunting for a spell.'],
    'quests-bestiary' => ['Quests and Bestiary', 'The Quest Log records supported chest discoveries and NPC missions for your character. Bestiary entries advance as you defeat creatures; completing an entry at 1,000 kills grants +0.2% permanent XP. The client shows progress and completed entries.'],
    'market-coins' => ['Market and Coins', 'The Market supports player offers for items and coins. Review an offer before accepting, and collect completed trades through the Market. Antigas Coins bought on the website are delivered to the selected character through Collect depot after manual payment approval.'],
    'client-support' => ['Client and support', 'Download the client from the home page and extract it to a folder you can write to. Antigas_gl.exe is ready to connect to this server. The Help channel is the first place to ask other players for assistance; staff commands are reserved for staff.'],
    'faq' => ['Frequently asked questions', 'Where do new characters start? In Rookgaard. Where do I download the client? Use the download button on the home page. Are website Coins instant? No: payment is reviewed manually, then collected in the Market. Where can I find the full spell list? Search the client or open the original community wiki.'],
];
?>
<!doctype html>
<html lang="<?= e(siteLanguageTag()) ?>">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="<?= siteT('Read the player guide in English or choose another language.') ?>">
  <link rel="canonical" href="https://tibia74.tech/wiki.php">
  <title><?= siteT('Wiki Antigas') ?> · Antigas 7.4</title>
  <link rel="stylesheet" href="/classic-2004.css?v=20260924-1">
  <link rel="stylesheet" href="/wiki.css?v=security-20260928">
  <link rel="stylesheet" href="/language.css?v=security-20260928">
  <link rel="stylesheet" href="/classic-refinement.css?v=classic-20261003-1">
</head>
<body class="wiki-page">
  <a class="skip-link" href="#wiki-content"><?= siteT('Skip to content') ?></a>
  <div class="skyline">
    <header class="masthead">
      <a class="wordmark" href="/" aria-label="Antigas 7.4 — <?= siteT('Home') ?>"><span>Antigas</span><i>7.4 CLASSIC</i></a>
      <p class="motto"><?= siteT('Wiki Antigas') ?></p>
    </header>
    <nav class="topnav" aria-label="<?= siteT('Main navigation') ?>">
      <a href="/"><?= siteT('Home') ?></a><a href="/wiki.php" aria-current="page"><?= siteT('Wiki Antigas') ?></a><a href="/account.php"><?= siteT('My account') ?></a><a href="/coins.php"><?= siteT('Buy coins') ?></a><a href="/Antigas-7.4-Launcher-v66.zip?site=achievement-ranks-v66-20261003"><?= siteT('Download') ?></a>
    </nav>
    <?= siteLanguageSwitcher() ?>
  </div>
  <div class="layout wiki-layout">
    <aside class="sidebar wiki-sidebar">
      <nav class="stone-menu" aria-label="<?= siteT('Wiki home') ?>">
        <h2><?= siteT('Wiki Antigas') ?></h2>
        <?php foreach ($sections as $id => [$title, $body]): ?><a href="#<?= e($id) ?>"><?= siteT($title) ?></a><?php endforeach; ?>
        <div class="side-rule" aria-hidden="true"></div>
        <a href="https://antigas-jogador-wiki.ricardozordan1994.chatgpt.site/#/home" target="_blank" rel="noopener noreferrer"><?= siteT('Original community wiki') ?> ↗</a>
      </nav>
    </aside>
    <main class="paper wiki-paper" id="wiki-content" tabindex="-1">
      <section class="page-title"><h1><?= siteT('Wiki Antigas') ?></h1><p><?= siteT('Read the player guide in English or choose another language.') ?></p></section>
      <details class="classic-index wiki-index">
        <summary><?= siteT('Player guide') ?></summary>
        <nav aria-label="<?= siteT('Player guide') ?>">
          <?php foreach ($sections as $id => [$title, $body]): ?><a href="#<?= e($id) ?>"><?= siteT($title) ?></a><?php endforeach; ?>
        </nav>
      </details>
      <div class="wiki-callout"><p><?= siteT('The local guide follows the current website and client release.') ?></p><a class="button" href="/Antigas-7.4-Launcher-v66.zip?site=achievement-ranks-v66-20261003"><?= siteT('Download Antigas 7.4 client') ?></a></div>
      <?php foreach ($sections as $id => [$title, $body]): ?>
        <section class="wiki-entry" id="<?= e($id) ?>">
          <h2><?= siteT($title) ?></h2>
          <p><?= siteT($body) ?></p>
          <?php if ($id === 'spells-runes'): ?><p><?= siteT('The full legacy spell guide remains available in the original community edition.') ?> <a href="https://antigas-jogador-wiki.ricardozordan1994.chatgpt.site/#/spells" target="_blank" rel="noopener noreferrer"><?= siteT('Open the original Wiki Antigas') ?> ↗</a></p><?php endif; ?>
          <?php if ($id === 'market-coins'): ?><p><?= siteT('See coin prices and create an order on the website.') ?> <a href="/coins.php"><?= siteT('Antigas Coins') ?></a></p><?php endif; ?>
        </section>
      <?php endforeach; ?>
      <section class="wiki-original">
        <h2><?= siteT('Original community wiki') ?></h2>
        <p><?= siteT('The original community guide is still available in its published edition.') ?></p>
        <a class="button button-secondary" href="https://antigas-jogador-wiki.ricardozordan1994.chatgpt.site/#/home" target="_blank" rel="noopener noreferrer"><?= siteT('Open the original Wiki Antigas') ?> ↗</a>
      </section>
      <footer><?= siteT('Wiki last checked: 28 September 2026') ?> · Antigas 7.4</footer>
    </main>
  </div>
</body>
</html>
