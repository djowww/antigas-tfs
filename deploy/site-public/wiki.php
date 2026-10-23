<?php
declare(strict_types=1);
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-cache');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: strict-origin-when-cross-origin');
header("Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
require __DIR__ . '/i18n.php';
siteStartI18n('pt');
function wikiEscape(string $value): string { return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
$github = 'https://github.com/djowww/tibia-7.4-a-classic-rpg-version';
$release = $github . '/releases/tag/local-test-v1';
$download = $github . '/releases/download/local-test-v1/Tibia74-Local-Complete.zip';
$updates = json_decode(file_get_contents(__DIR__ . '/project-updates.json'), true, 512, JSON_THROW_ON_ERROR);
function projectSourceUrl(string $url, string $repository): string {
    // Editorial links may only point to this project's HTTPS GitHub pages.
    return $url === $repository || str_starts_with($url, $repository . '/') ? $url : $repository;
}
$sections = [
    'getting-started' => ['Getting started', 'Create an account on this site, download the configured client and start your first character in Rookgaard. Keep your account number and password private. Use Help for questions, Trade to advertise trades and World Chat for general conversation.'],
    'vocations' => ['Vocations and promotion', 'Sorcerers and Druids gain 5 health, 30 mana and 10 capacity per level. Paladins gain 10 health, 15 mana and 20 capacity. Knights gain 15 health, 5 mana and 25 capacity. Promotions are Master Sorcerer, Elder Druid, Royal Paladin and Elite Knight.'],
    'online-bonus' => ['Online bonus', 'Each full continuous hour online grants +0.2% experience and skill bonus, up to 5%. Logging out before the next full hour does not add that hour. The bonus is saved for your character.'],
    'combat-pvp' => ['Combat and PvP', 'Attack, Balanced and Defense fighting modes change your physical weapon damage and protection trade-off. Use !frags to check kill counts and !pz to check your protection-zone lock. Follow the server rules when fighting other players.'],
    'spells-runes' => ['Spells and runes', 'Use the client spell list to search by name, vocation and required level. Instant spells consume mana; runes are created by casting a rune spell while carrying the required blank rune. Check your vocation and level before hunting for a spell.'],
    'quests-bestiary' => ['Quests and Bestiary', 'The Quest Log records supported chest discoveries and NPC missions for your character. Bestiary entries advance as you defeat creatures; completing an entry at 1,000 kills grants +0.2% permanent XP. The client shows progress and completed entries.'],
    'market-coins' => ['Market and Coins', 'The Market supports player offers for items and coins. Review an offer before accepting, and collect completed trades through the Market. Website purchases are disabled.'],
    'client-support' => ['Client and support', 'Download the client from the home page and extract it to a folder you can write to. Antigas_gl.exe is ready to connect to this server. The Help channel is the first place to ask other players for assistance; staff commands are reserved for staff.'],
    'faq' => ['Frequently asked questions', 'New characters start in Rookgaard. Download the client on the home page. Website purchases are disabled. Find spells in the client or in the Spells and runes section.'],
];
?>
<!doctype html>
<html lang="<?= wikiEscape(siteLanguageTag()) ?>">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="<?= siteT('The project website: news, changelog, downloads and the player wiki.') ?>">
  <link rel="canonical" href="https://tibia74.tech/">
  <title>Tibia 7.4 — A classic rpg version</title>
  <link rel="stylesheet" href="/classic-2004.css?v=20260924-1">
  <link rel="stylesheet" href="/language.css?v=security-20260928">
  <link rel="stylesheet" href="/classic-refinement.css?v=classic-20261003-1">
  <link rel="stylesheet" href="/wiki.css?v=project-home-20261023-1">
</head>
<body class="wiki-page project-home">
  <a class="skip-link" href="#wiki-content"><?= siteT('Skip to content') ?></a>
  <div class="skyline">
    <header class="masthead">
      <a class="wordmark" href="/" aria-label="Tibia 7.4 — <?= siteT('Home') ?>"><span>Tibia 7.4</span><i>A CLASSIC RPG VERSION</i></a>
      <p class="motto"><?= siteT('Open source project') ?></p>
    </header>
    <nav class="topnav" aria-label="<?= siteT('Main navigation') ?>">
      <a href="/" aria-current="page"><?= siteT('Home') ?></a><a href="#novidades"><?= siteT('News') ?></a><a href="#changelog">Changelog</a><a href="#guia"><?= siteT('Player guide') ?></a><a href="#download"><?= siteT('Download') ?></a><a href="<?= wikiEscape($github) ?>">GitHub</a>
    </nav>
    <?= siteLanguageSwitcher() ?>
  </div>
  <div class="layout wiki-layout">
    <aside class="sidebar wiki-sidebar">
      <nav class="stone-menu" aria-label="<?= siteT('Project and wiki') ?>">
        <h2><?= siteT('The project') ?></h2>
        <a href="#novidades"><?= siteT('News') ?></a><a href="#changelog">Changelog</a><a href="#download"><?= siteT('Download and test') ?></a><a href="<?= wikiEscape($github) ?>"><?= siteT('Source on GitHub') ?></a>
        <div class="side-rule" aria-hidden="true"></div>
        <h2 class="wiki-menu-title"><?= siteT('Player guide') ?></h2>
        <?php foreach ($sections as $id => [$title, $body]): ?><a href="#<?= wikiEscape($id) ?>"><?= siteT($title) ?></a><?php endforeach; ?>
        <div class="side-rule" aria-hidden="true"></div>
        <a href="/index.php?jogar=1#criar-conta"><?= siteT('Create account') ?></a><a href="/account.php"><?= siteT('My account') ?></a>
      </nav>
    </aside>
    <main class="paper wiki-paper" id="wiki-content" tabindex="-1">
      <section class="page-title project-title"><h1>Tibia 7.4</h1><p class="project-subtitle">A classic rpg version</p><p><?= siteT('The project website: news, changelog, downloads and the player wiki.') ?></p></section>
      <div class="wiki-callout project-welcome"><div><p><?= siteT('A classic world, shared with the community.') ?></p><p class="project-small"><?= siteT('Explore the code, follow important releases or run your own world in localhost.') ?></p><div class="project-actions"><a class="button" href="<?= wikiEscape($download) ?>"><?= siteT('Download server + Windows client') ?></a><a class="project-github" href="<?= wikiEscape($github) ?>"><?= siteT('Source on GitHub') ?></a></div><p class="project-small"><?= siteT('Local test: account {account}, password {password}. Docker Desktop is required.', ['account'=>'1','password'=>'local123']) ?></p></div></div>
      <section class="project-news" id="novidades" aria-labelledby="news-title">
        <h2 id="news-title"><?= siteT('Project news') ?></h2>
        <p class="project-small"><?= siteT('Important releases and game changes, selected from the repository.') ?></p>
        <div id="changelog" class="project-changelog">
          <?php foreach ($updates as $update): ?>
          <article class="project-update" id="<?= wikiEscape($update['id']) ?>">
            <h3 class="news-ribbon"><time datetime="<?= wikiEscape($update['date']) ?>"><?= wikiEscape(date('d.m.Y', strtotime($update['date']))) ?></time><span><?= siteT($update['title']) ?></span></h3>
            <div class="news-body"><p><?= siteT($update['summary']) ?></p><h4><?= siteT('What changed') ?></h4><ul class="gold-list"><?php foreach ($update['changes'] as $change): ?><li><?= siteT($change) ?></li><?php endforeach; ?></ul>
              <details class="project-details"><summary><?= siteT('Details and validation') ?></summary><?php foreach ($update['paragraphs'] as $paragraph): ?><p><?= siteT($paragraph) ?></p><?php endforeach; ?></details>
              <p><a href="<?= wikiEscape(projectSourceUrl($update['url'], $github)) ?>"><?= siteT('Read on GitHub') ?></a></p>
            </div>
          </article>
          <?php endforeach; ?>
        </div>
      </section>
      <section class="wiki-entry project-download" id="download" aria-labelledby="download-title">
        <h2 id="download-title"><?= siteT('Download and test') ?></h2><p><?= siteT('The complete localhost package includes the server and the Windows .exe client.') ?></p>
        <p class="project-actions"><a class="button" href="<?= wikiEscape($download) ?>"><?= siteT('Download complete package') ?></a><a href="<?= wikiEscape($release) ?>"><?= siteT('Release notes and checksums') ?></a></p>
        <ol><li><?= siteT('Open Docker Desktop in Linux container mode.') ?></li><li><?= siteT('Extract the package and run START-LOCAL.cmd. The first setup needs internet.') ?></li><li><?= siteT('Log in with the demo account below. Use STOP-LOCAL.cmd to stop without deleting progress.') ?></li></ol>
        <div class="project-demo"><h3><?= siteT('Localhost demo account') ?></h3><dl><div><dt><?= siteT('Account number') ?></dt><dd>1</dd></div><div><dt><?= siteT('Password') ?></dt><dd>local123</dd></div><div><dt><?= siteT('Character') ?></dt><dd>Local Adventurer</dd></div></dl><p><?= siteT('Only for your local installation. This account has no GM privileges and does not access the public server.') ?></p></div>
        <p class="project-small" id="criar-conta"><?= siteT('Prefer the public server? Use your own account and the online client.') ?> <a href="/index.php?jogar=1#download"><?= siteT('Online client and registration') ?></a> · <a href="/index.php?jogar=1#criar-conta"><?= siteT('Create account') ?></a></p>
      </section>
      <section class="wiki-entry project-guide-title" id="guia"><h2><?= siteT('Player guide') ?></h2><p><?= siteT('Use the wiki to learn about the world and its game systems.') ?></p></section>
      <details class="classic-index wiki-index"><summary><?= siteT('Player guide') ?></summary><nav aria-label="<?= siteT('Player guide') ?>"><?php foreach ($sections as $id => [$title, $body]): ?><a href="#<?= wikiEscape($id) ?>"><?= siteT($title) ?></a><?php endforeach; ?></nav></details>
      <?php foreach ($sections as $id => [$title, $body]): ?>
        <section class="wiki-entry" id="<?= wikiEscape($id) ?>"><h2><?= siteT($title) ?></h2><p><?= siteT($body) ?></p></section>
      <?php endforeach; ?>
      <footer>Tibia 7.4 — A classic rpg version · <?= siteT('Independent community project, inspired by Tibia. Not affiliated with CipSoft.') ?><br><a href="<?= wikiEscape($github) ?>">GitHub</a> · <a href="<?= wikiEscape($github) ?>/blob/main/NOTICE.md"><?= siteT('Credits and licenses') ?></a></footer>
    </main>
  </div>
</body>
</html>
