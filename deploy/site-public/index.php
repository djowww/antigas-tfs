<?php
declare(strict_types=1);
require (getenv('ANTIGAS_WEB_LIB')?:'/opt/antigas-web/private').'/security.php';
webStart();
require __DIR__.'/i18n.php';
$language=siteStartI18n();
function e(string $v): string { return htmlspecialchars($v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
$message='';$messageType='info';$accountName='';$email='';$characterName='';$sex='1';
$downloadUrl='https://tibia74.tech/Antigas-7.4-Client-v45.zip?site=loot-20260928';
if ($_SERVER['REQUEST_METHOD']==='POST') {
    $accountName=trim(webField('account_name',9));
    $email=trim(webField('email',255));
    $characterName=preg_replace('/ +/',' ',trim(webField('character_name',80)));
    $sex=webField('sex',1);
    $password=webField('password',64);
    $pdo=null;
    try {
        if (webField('website')!=='' || isset($_POST['website']) && !is_string($_POST['website'])) throw new DomainException(siteTranslation('Registration could not be completed.'));
        if (!hash_equals($_SESSION['csrf'],webField('csrf',64))) throw new DomainException(siteTranslation('Your form session has expired. Refresh the page and try again.'));
        if (!webLimit('register:'.($_SERVER['REMOTE_ADDR']??'unknown'),5,3600)) throw new DomainException(siteTranslation('Too many attempts right now. Wait one hour and try again.'));
        if (!preg_match('/\\A[1-9][0-9]{5,8}\\z/D',$accountName)) throw new DomainException(siteTranslation('Choose a 6 to 9 digit account number without a leading zero.'));
        if (!webName($characterName) || !in_array($sex,['0','1'],true)) throw new DomainException(siteTranslation('Choose a 3 to 25 letter-and-space character name, with no administrative titles.'));
        if ($email!=='' && !filter_var($email,FILTER_VALIDATE_EMAIL)) throw new DomainException(siteTranslation('Enter a valid email address or leave the field blank.'));
        if (!webPassword($password)) throw new DomainException(siteTranslation('Use a password of 8 to 64 characters with no control characters.'));
        if (!hash_equals($password,webField('password_confirm',64))) throw new DomainException(siteTranslation('Passwords do not match.'));
        $pdo=webDb();$pdo->beginTransaction();
        // Account type and player group come from NORMAL database defaults.
        // The web database user cannot insert/update those privilege columns.
        $q=$pdo->prepare('INSERT INTO accounts (id,password,email,created) VALUES (?,?,?,?)');
        $q->execute([(int)$accountName,sha1($password),$email,time()]);
        $q=$pdo->prepare("INSERT INTO players (name,account_id,level,vocation,health,healthmax,conditions,cap,sex,looktype,lookhead,lookbody,looklegs,lookfeet,soul,town_id,posx,posy,posz,comment,created) VALUES (?,?,1,0,150,150,'',400,?,?,78,69,58,76,100,11,32097,32219,7,'',UNIX_TIMESTAMP())");
        $q->execute([$characterName,(int)$accountName,(int)$sex,$sex==='1'?128:136]);
        $pdo->commit();
        $message=siteTranslation('Account {account} created! {character} is waiting for you in Rookgaard. Log into the client with this number and your chosen password.',['account'=>$accountName,'character'=>$characterName]);
        $messageType='success';$accountName='';$email='';$characterName='';
        $_SESSION['csrf']=bin2hex(random_bytes(32));
    } catch (DomainException $ex) {
        if ($pdo && $pdo->inTransaction()) $pdo->rollBack();
        $message=$ex->getMessage();$messageType='error';
    } catch (Throwable $ex) {
        if ($pdo && $pdo->inTransaction()) $pdo->rollBack();
        $message=siteTranslation($ex instanceof PDOException && (string)$ex->getCode()==='23000'?'The account number or character name is already in use.':'Registration is temporarily unavailable.');
        error_log('Antigas registration: '.get_class($ex).' code '.$ex->getCode());
        $messageType='error';
    }
}
?>
<!doctype html>
<html lang="<?= e(siteLanguageTag()) ?>">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#090b17">
  <meta name="description" content="<?= siteT('Enter a classic world inspired by Tibia 7.4. Create an account and download the client.') ?>">
  <link rel="canonical" href="https://tibia74.tech/">
  <title><?= siteT('Antigas 7.4 — A new adventure') ?></title>
  <link rel="stylesheet" href="/classic-2004.css?v=20260924-1">
  <link rel="stylesheet" href="/home-improvements.css?v=20260927-2">
  <link rel="stylesheet" href="/news-changelog.css?v=20260927-1">
  <link rel="stylesheet" href="/language.css?v=security-20260928">
</head>
<body class="portal-home">
  <a class="skip-link" href="#conteudo"><?= siteT('Skip to content') ?></a>
  <div class="skyline">
    <header class="masthead">
      <a class="wordmark" href="/" aria-label="Antigas 7.4 — <?= siteT('Home') ?>"><span>Antigas</span><i>7.4 CLASSIC</i></a>
      <p class="motto"><?= siteTHtml('A world of adventures.<br><span>Like the old days.</span>') ?></p>
    </header>
    <nav class="topnav" aria-label="<?= siteT('Main navigation') ?>">
      <a href="#inicio" aria-current="page"><?= siteT('Home') ?></a><a href="#noticias"><?= siteT('News') ?></a><a href="#mundo"><?= siteT('The world') ?></a><a href="#market">Market</a><a href="/account.php"><?= siteT('My account') ?></a><a href="/coins.php"><?= siteT('Buy coins') ?></a><a href="#criar-conta"><?= siteT('Create account') ?></a><a href="#download"><?= siteT('Download') ?></a>
    </nav>
    <?= siteLanguageSwitcher() ?>
  </div>

  <div class="layout" id="inicio">
    <aside class="sidebar">
      <nav class="stone-menu" aria-label="<?= siteT('Player guide') ?>">
        <h2><?= siteT('Player guide') ?></h2>
        <a href="#noticias"><?= siteT('Latest news') ?></a>
        <a href="#primeiros-passos"><?= siteT('Getting started') ?></a>
        <a href="/wiki.php" aria-label="<?= siteT('Game wiki') ?>"> <?= siteT('Game wiki') ?> ↗</a>
        <a href="#sobre"><?= siteT('About Antigas') ?></a>
        <div class="side-rule" aria-hidden="true"></div>
      </nav>
      <p class="side-signature">Antigas<span>7.4</span></p>
      <section class="world-note" aria-labelledby="world-heading">
        <h2 id="world-heading"><?= siteT('Our world') ?></h2>
        <dl><div><dt><?= siteT('Version') ?></dt><dd>7.4</dd></div><div><dt><?= siteT('Start') ?></dt><dd>Rookgaard</dd></div></dl>
        <p class="world-caption"><?= siteTHtml('Old roads.<br>New stories.') ?></p>
      </section>
      <nav class="side-news" aria-label="<?= siteT('Featured news') ?>">
        <h2><?= siteT('On the notice board') ?></h2>
        <a href="#objectives-v43"><?= siteT('Your next goal') ?><time datetime="2026-09-28"><?= siteT('28 Sep 2026') ?></time></a>
        <a href="#menu-v42"><?= siteT('A menu that suits you') ?><time datetime="2026-09-28"><?= siteT('28 Sep 2026') ?></time></a>
        <a href="#achievement-objectives"><?= siteT('See every objective') ?><time datetime="2026-09-28"><?= siteT('28 Sep 2026') ?></time></a>
        <a href="#achievements"><?= siteT('Achievements to pursue') ?><time datetime="2026-09-27"><?= siteT('27 Sep 2026') ?></time></a>
        <a href="#bestiary-xp"><?= siteT('Bestiary XP bonus') ?><time datetime="2026-09-27"><?= siteT('27 Sep 2026') ?></time></a>
        <a href="#questlog"><?= siteT('Quest Log in the client') ?><time datetime="2026-09-27"><?= siteT('27 Sep 2026') ?></time></a>
        <a href="#bestiary"><?= siteT('Explore the Bestiary') ?><time datetime="2026-09-26"><?= siteT('26 Sep 2026') ?></time></a>
        <a href="#hunt"><?= siteT('Hunt and online bonus') ?><time datetime="2026-09-25"><?= siteT('25 Sep 2026') ?></time></a>
        <a href="#market"><?= siteT('The Market is here') ?><time datetime="2026-09-24"><?= siteT('24 Sep 2026') ?></time></a>
        <a href="#mundo"><?= siteT('The world is open') ?><time datetime="2026-09-23"><?= siteT('23 Sep 2026') ?></time></a>
      </nav>
    </aside>

    <main class="paper" id="conteudo" tabindex="-1">
      <section class="welcome" id="boas-vindas" aria-labelledby="welcome-heading">
        <div class="welcome-copy">
          <p class="eyebrow"><?= siteT('Classic Tibia 7.4') ?></p>
          <h1 id="welcome-heading"><?= siteT('Your adventure starts here') ?></h1>
          <p class="intro"><?= siteT('Gather your friends, explore caves and write your story. The world of Antigas is waiting, just like the old days.') ?></p>
          <div class="welcome-actions"><a class="button" href="#criar-conta"><?= siteT('Create account') ?></a><a class="button button-secondary" href="#download"><?= siteT('Download the client') ?></a><a class="button button-secondary" href="/wiki.php" aria-label="<?= siteT('Game wiki') ?>"><?= siteT('Game wiki ↗') ?></a></div>
          <ol class="journey-steps" aria-label="<?= siteT('How to begin') ?>"><li><b aria-hidden="true">1</b><a href="#criar-conta"><?= siteT('Create your account') ?></a></li><li><b aria-hidden="true">2</b><a href="#download"><?= siteT('Download the client') ?></a></li><li><b aria-hidden="true">3</b><a href="#primeiros-passos"><?= siteT('Enter the world') ?></a></li></ol>
        </div>
        <div class="welcome-crest" aria-hidden="true"><img src="/classic-assets/crest.svg" width="126" height="142" alt=""><span>7.4 Classic</span></div>
      </section>
      <section class="page-title" id="noticias"><h2><?= siteT('Latest news') ?></h2><p><?= siteT('New systems and improvements in the world of Antigas 7.4.') ?></p></section>
      <article id="objectives-v43" class="news-article update-article">
        <h3 class="news-ribbon"><span><?= siteT('Your next goal') ?></span><time datetime="2026-09-28"><?= siteT('28 Sep 2026 · Client v43') ?></time></h3>
        <div class="news-body">
          <p class="dropcap"><?= siteTHtml('The <strong>Achievements</strong> panel now highlights the next goal in each category and shows your percentage and remaining progress. <strong>All objectives</strong> still displays all 60 achievements.') ?></p>
          <p><?= siteTHtml('If you run out of space or capacity, your reward is saved as pending. Make room and click <strong>Claim rewards</strong> to collect it; you do not need to gain another level. Items are never dropped on the ground.') ?></p>
          <p><?= siteT('The scroll grants 25% XP for one hour. The panel also explains which bonuses affect direct damage.') ?></p>
        </div>
      </article>
      <article id="menu-v42" class="news-article update-article">
        <h3 class="news-ribbon"><span><?= siteT('Menu, your way') ?></span><time datetime="2026-09-28"><?= siteT('28 Sep 2026 · Client v42') ?></time></h3>
        <div class="news-body">
          <p class="dropcap"><?= siteTHtml('Click the <strong>Menu [-]</strong> heading to collapse the buttons or <strong>Menu [+]</strong> to expand them. The control is larger, spacing is consistent and new achievements stay highlighted even while the menu is collapsed.') ?></p>
          <p><?= siteT('Your menu choice is saved between sessions. Download client v42 for this fix.') ?></p>
        </div>
      </article>
      <article id="achievement-objectives" class="news-article update-article">
        <h3 class="news-ribbon"><span><?= siteT('Choose your next achievement') ?></span><time datetime="2026-09-28"><?= siteT('28 Sep 2026 · Client v41') ?></time></h3>
        <div class="news-body">
          <p class="dropcap"><?= siteTHtml('The <strong>Achievements</strong> panel now shows all 60 available goals, including each achievement\'s target, progress and reward. Use the category and completion filters to choose what to pursue next.') ?></p>
          <p><?= siteT('The list stays visible while it updates, and the side menu now has an easy-to-find control to collapse or expand its buttons. Download client v41 for these fixes.') ?></p>
        </div>
      </article>
      <article id="achievements" class="news-article update-article">
        <h3 class="news-ribbon"><span><?= siteT('Achievements, progress and rewards') ?></span><time datetime="2026-09-27"><?= siteT('27 Sep 2026 · Client v40') ?></time></h3>
        <div class="news-body">
          <p class="dropcap"><?= siteTHtml('The new <strong>Achievements</strong> panel tracks steps, monsters defeated, deaths, PvP victories, levels and skills. Its button highlights new achievements until you open the panel, and the side menu can be collapsed or expanded.') ?></p>
          <p><?= siteT('Milestones grant permanent bonuses to speed, physical and magic damage, PvP damage and experience lost on death. Levels grant experience scrolls, while skills grant matching training weapons. Progress and rewards are saved per character.') ?></p>
        </div>
      </article>
      <article id="bestiary-xp" class="news-article update-article">
        <h3 class="news-ribbon"><span><?= siteT('Reward for a completed Bestiary') ?></span><time datetime="2026-09-27"><?= siteT('27 Sep 2026 · Client v40') ?></time></h3>
        <div class="news-body">
          <p class="dropcap"><?= siteTHtml('Complete 1,000 kills of a creature to receive <strong>+0.2% permanent experience</strong> for each completed Bestiary entry.') ?></p>
          <p><?= siteT('The bonus stacks across creatures. The Bestiary shows your current total, and previous completions are synchronized automatically when you log in.') ?></p>
        </div>
      </article>
      <article id="questlog" class="news-article update-article">
        <h3 class="news-ribbon"><span><?= siteT('Your adventure log: Quest Log') ?></span><time datetime="2026-09-27"><?= siteT('27 Sep 2026 · Client v35') ?></time></h3>
        <div class="news-body">
          <p class="dropcap"><?= siteTHtml('Quests are easier to follow. Open <strong>Quests</strong> on the client sidebar or press <strong>Ctrl+J</strong> to search the Quest Log, filter missions and review the steps recorded for your character.') ?></p>
          <p><?= siteT('The log combines map chest records and NPC missions. Progress is personal and refreshes while the window is open. Rewards are still earned in the game world, as usual.') ?></p>
          <p class="news-note"><?= siteT('Some chests only record quest completion; the log shows only the steps the server can confirm.') ?></p>
        </div>
      </article>

      <figure class="systems-illustration">
        <img src="/classic-assets/adventure-systems.svg" width="960" height="290" loading="lazy" alt="<?= siteT('Classic illustration: Market coins, the Bestiary book and a quest log.') ?>">
        <figcaption><?= siteT('New tools to trade, learn about creatures and follow your adventures.') ?></figcaption>
      </figure>

      <article id="bestiary" class="news-article update-article">
        <h3 class="news-ribbon"><span><?= siteT('Meet the creatures in the Bestiary') ?></span><time datetime="2026-09-26"><?= siteT('26 Sep 2026 · Client v32') ?></time></h3>
        <div class="news-body">
          <p class="dropcap"><?= siteT('The creature encyclopedia has a refreshed interface in the classic Tibia style. Browse creature details and loot, search by name and move through the cards without losing your place in the list.') ?></p>
          <p><?= siteT('Your character\'s kills feed Bestiary progress, with filters for creatures in progress and completed entries. The server\'s existing records track up to 1,000 kills per creature.') ?></p>
        </div>
      </article>

      <article id="client-shop" class="news-article update-article">
        <h3 class="news-ribbon"><span><?= siteT('A Shop refreshed with Antigas branding') ?></span><time datetime="2026-09-27"><?= siteT('27 Sep 2026 · Client v34') ?></time></h3>
        <div class="news-body">
          <p class="dropcap"><?= siteT('The Shop now has an Antigas crest, better-aligned lists and original sprites. Category navigation, product details, history and confirmations are clearer.') ?></p>
          <p><?= siteT('The classic client keeps evolving through incremental releases, with its old-school look and no extra installation required.') ?></p>
        </div>
      </article>

      <article id="hunt" class="news-article update-article">
        <h3 class="news-ribbon"><span><?= siteT('Hunt: track your session and progress') ?></span><time datetime="2026-09-25"><?= siteT('25 Sep 2026 · Client v17') ?></time></h3>
        <div class="news-body">
          <p class="dropcap"><?= siteT('The Hunt panel brings together experience, session pace, loot collected and supplies used while hunting. These session counters help you follow your adventure.') ?></p>
          <p><?= siteTHtml('Time online also grants a stacking bonus: <strong>+0.2% experience and skills</strong> each hour, up to <strong>5%</strong>. Base experience, skill and loot rates are 1×.') ?></p>
          <p><?= siteT('The world channels are World Chat, Trade and Help. You can control shared party experience in the client; administrative commands are restricted to staff.') ?></p>
        </div>
      </article>

      <article id="market" class="news-article">
        <h3 class="news-ribbon"><span><?= siteT('Market: player-to-player offers') ?></span><time datetime="2026-09-24"><?= siteT('24 Sep 2026') ?></time></h3>
        <div class="news-body">
          <p class="dropcap"><?= siteT('Find items, compare offers and trade with other players directly through the client. The catalog has search, categories and filters for buying and selling.') ?></p>
          <ul class="gold-list"><li><?= siteTHtml('<strong>Gold:</strong> payments include gold, platinum and crystal coins, as well as your bank balance.') ?></li><li><?= siteTHtml('<strong>Antigas Coin:</strong> a separate currency shown on each offer.') ?></li><li><?= siteTHtml('<strong>History and collection:</strong> follow offers and trades; use <strong>Collect</strong> to claim them. Gold goes to the bank; items and Antigas Coins go to the depot.') ?></li></ul>
          <p><?= siteT('Trades are recorded, and sale proceeds are reserved for the seller until collected.') ?></p>
          <p><?= siteT('Interrupted operations and simultaneous Market access are handled more carefully to protect player trades.') ?></p>
        </div>
      </article>
      <article id="mundo" class="news-article">
      <h3 class="news-ribbon"><span><?= siteT('The world is open for new adventures') ?></span><time datetime="2026-09-23"><?= siteT('23 Sep 2026') ?></time></h3>
      <section class="content-section" id="primeiros-passos">
        <h4><?= siteT('Begin your journey') ?></h4>
        <p><?= siteT('From the streets of Thais to the tunnels of Rookgaard, rediscover a world of exploration. No shortcuts: a rope, a torch and curiosity are a good start.') ?></p>
        <p><?= siteTHtml('Create your account and first character here. Then download the client, extract the archive and open <strong>Antigas_gl.exe</strong>. The server address is already configured.') ?></p>
      </section>
      </article>

      <section class="account-section" id="criar-conta">
        <div class="section-heading"><h2><?= siteT('Create account') ?></h2><p><?= siteT('Your first character starts in Rookgaard.') ?></p></div>
        <?php if ($message !== ''): ?><div class="notice <?= e($messageType) ?>" role="status"><?= e($message) ?></div><?php endif; ?>
        <form method="post" action="#criar-conta" autocomplete="on">
          <input type="hidden" name="csrf" value="<?= e((string)$_SESSION['csrf']) ?>">
          <div class="trap" aria-hidden="true"><label><?= siteT('Leave this field empty') ?><input name="website" tabindex="-1" autocomplete="off"></label></div>
          <label for="account_name"><?= siteT('Account number') ?></label>
          <input id="account_name" name="account_name" value="<?= e($accountName) ?>" required minlength="6" maxlength="9" pattern="[1-9][0-9]{5,8}" inputmode="numeric" autocomplete="username" placeholder="<?= siteT('e.g. 734215') ?>" aria-describedby="account-help">
          <small id="account-help"><?= siteT('Choose a 6 to 9 digit number. You will use it to log into the game.') ?></small>
          <label for="character_name"><?= siteT('Character name') ?></label>
          <input id="character_name" name="character_name" value="<?= e($characterName) ?>" required minlength="3" maxlength="25" pattern="[A-Za-z][A-Za-z ]{2,24}" placeholder="<?= siteT('e.g. Darian') ?>">
          <label for="sex"><?= siteT('Initial appearance') ?></label>
          <select id="sex" name="sex"><option value="1" <?= $sex === '1' ? 'selected' : '' ?>><?= siteT('Male') ?></option><option value="0" <?= $sex === '0' ? 'selected' : '' ?>><?= siteT('Female') ?></option></select>
          <label for="email"><?= siteT('Email') ?> <span>(<?= siteT('Optional') ?>)</span></label>
          <input id="email" name="email" type="email" value="<?= e($email) ?>" maxlength="255" autocomplete="email" placeholder="<?= siteT('you@example.com') ?>">
          <label for="password"><?= siteT('Password') ?></label>
          <input id="password" name="password" type="password" required minlength="8" maxlength="64" autocomplete="new-password" aria-describedby="password-help">
          <label for="password_confirm"><?= siteT('Confirm password') ?></label>
          <input id="password_confirm" name="password_confirm" type="password" required minlength="8" maxlength="64" autocomplete="new-password" aria-describedby="password-help">
          <p class="password-note" id="password-help"><?= siteT('Use 8 to 64 characters and a unique password for this server. Do not reuse your email or other service password.') ?></p>
          <button class="button primary" type="submit"><?= siteT('Create account and character') ?></button>
        </form>
      </section>

      <section class="download-section" id="download">
        <div><h2><?= siteT('Classic client') ?></h2><p><?= siteT('Download the client configured for this server. No extra software is needed.') ?></p></div>
        <a class="button download-button" href="<?= e($downloadUrl) ?>"><?= siteT('Download Antigas 7.4 client') ?></a>
      </section>
      <footer id="sobre"><?= siteTHtml('Antigas 7.4 — An independent community project, not affiliated with CipSoft.<br>Tibia is a trademark of its respective owners.') ?></footer>
    </main>
  </div>
</body>
</html>
