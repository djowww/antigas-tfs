<?php
declare(strict_types=1);
require (getenv('ANTIGAS_WEB_LIB')?:'/opt/antigas-web/private').'/security.php';
webStart();
require __DIR__.'/i18n.php';
$language=siteStartI18n();
function e($value): string { return htmlspecialchars((string)$value,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
function field(string $name): string { return webField($name); }
function limitAttempt(string $key,int $limit): bool { return webLimit($key,$limit); }
$message=''; $error=false; $account=null; $characters=[]; $pdo=null;
try {
    $pdo=webDb();
    $account=webAccount($pdo);
    if ($_SERVER['REQUEST_METHOD']==='POST') {
        if (!hash_equals($_SESSION['csrf'],field('csrf'))) throw new DomainException(siteTranslation('Your form has expired. Refresh the page.'));
        $action=field('action');
        if ($action==='logout') {
            $_SESSION=[]; session_regenerate_id(true); $_SESSION['csrf']=bin2hex(random_bytes(32));
            header('Location: /account.php',true,303); exit;
        }
        $ip=(string)($_SERVER['REMOTE_ADDR']??'unknown');
        if (!limitAttempt('ip:'.$ip,30)) throw new DomainException(siteTranslation('Too many attempts. Wait 15 minutes.'));
        if ($action==='login') {
            $id=trim(field('account')); $password=field('password');
            if (!preg_match('/^[1-9][0-9]{0,8}$/D',$id) || strlen($password)>64) throw new DomainException(siteTranslation('Incorrect account number or password.'));
            if (!limitAttempt('login:'.$id,10)) throw new DomainException(siteTranslation('Too many attempts. Wait 15 minutes.'));
            $q=$pdo->prepare('SELECT id,password,premdays,premium_points,blocked FROM accounts WHERE id=?'); $q->execute([$id]); $row=$q->fetch();
            // SHA-1 is required by the existing game server; never store plaintext.
            if (!$row || !hash_equals($row['password'],sha1($password)) || $row['blocked']) throw new DomainException(siteTranslation('Incorrect account number or password.'));
            session_regenerate_id(true); $_SESSION['account_id']=(int)$row['id']; $_SESSION['credential_tag']=hash('sha256',$row['password']); $_SESSION['seen']=time(); $_SESSION['csrf']=bin2hex(random_bytes(32));
            header('Location: /account.php',true,303); exit;
        }
        if (!$account) throw new DomainException(siteTranslation('Sign in to your account to continue.'));
        if ($action==='password') {
            $next=field('new_password');
            if (!hash_equals($account['password'],sha1(field('current_password')))) throw new DomainException(siteTranslation('The current password is incorrect.'));
            if (!webPassword($next) || !hash_equals($next,field('confirm_password'))) throw new DomainException(siteTranslation('Use a password of 8 to 64 characters and confirm the same value.'));
            $q=$pdo->prepare('UPDATE accounts SET password=? WHERE id=? AND password=?'); $q->execute([sha1($next),$account['id'],$account['password']]);
            if ($q->rowCount()===0 && !hash_equals($account['password'],sha1($next))) throw new DomainException(siteTranslation('Your account changed in another session. Please sign in again.'));
            $account['password']=sha1($next); $_SESSION['credential_tag']=hash('sha256',$account['password']); session_regenerate_id(true);
            $message=siteTranslation('Password updated. Use the new password on the website and in the game.');
        } elseif ($action==='character') {
            $name=preg_replace('/ +/',' ',trim(field('name'))); $sex=field('sex');
            if (!webName($name) || !in_array($sex,['0','1'],true)) throw new DomainException(siteTranslation('Choose a character name of 3 to 25 letters, with no administrative titles.'));
            $pdo->beginTransaction();
            $q=$pdo->prepare('SELECT id,password,blocked FROM accounts WHERE id=? FOR UPDATE'); $q->execute([$account['id']]);
            $locked=$q->fetch();
            if (!$locked || $locked['blocked'] || !hash_equals($account['password'],$locked['password'])) throw new DomainException(siteTranslation('Your account changed in another session. Please sign in again.'));
            $q=$pdo->prepare('SELECT COUNT(*) FROM players WHERE account_id=? AND deleted=0'); $q->execute([$account['id']]);
            if ((int)$q->fetchColumn()>=8) throw new DomainException(siteTranslation('You can have up to 8 characters per account.'));
            $q=$pdo->prepare("INSERT INTO players (name,account_id,level,vocation,health,healthmax,conditions,cap,sex,looktype,lookhead,lookbody,looklegs,lookfeet,soul,town_id,posx,posy,posz,comment,created) VALUES (?,?,1,0,150,150,'',400,?,?,78,69,58,76,100,11,32097,32219,7,'',UNIX_TIMESTAMP())");
            $q->execute([$name,$account['id'],(int)$sex,$sex==='1'?128:136]); $pdo->commit();
            $message=siteTranslation('{name} was created in Rookgaard at level 1, without privileges.',['name'=>$name]);
        } else { throw new DomainException(siteTranslation('Invalid action.')); }
        $_SESSION['csrf']=bin2hex(random_bytes(32));
    }
} catch (DomainException $ex) {
    if ($pdo && $pdo->inTransaction()) $pdo->rollBack(); $message=$ex->getMessage(); $error=true;
} catch (Throwable $ex) {
    if ($pdo && $pdo->inTransaction()) $pdo->rollBack();
    $message=siteTranslation($ex instanceof PDOException && (string)$ex->getCode()==='23000'?'Character name is already in use.':'The account service is temporarily unavailable.');
    error_log('Antigas account manager: '.get_class($ex).' code '.$ex->getCode()); $error=true;
}
if ($account && $pdo) {
    try { $q=$pdo->prepare('SELECT name,level,vocation FROM players WHERE account_id=? AND deleted=0 ORDER BY name'); $q->execute([$account['id']]); $characters=$q->fetchAll(); }
    catch (Throwable $ex) { $message=siteTranslation('Could not load your characters.'); $error=true; }
}
?>
<!doctype html><html lang="<?= e(siteLanguageTag()) ?>"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title><?= siteT('My account — Antigas 7.4') ?></title><link rel="stylesheet" href="/style.css?v=impeccable-20261001"><link rel="stylesheet" href="/account.css"><link rel="stylesheet" href="/language.css?v=security-20260928"></head>
<body><div class="skyline"><header class="masthead"><a class="wordmark" href="/"><span>Antigas</span><i>7.4 CLASSIC</i></a><p class="motto"><?= siteT('Your next adventure starts here.') ?></p></header><nav class="topnav" aria-label="<?= siteT('Main navigation') ?>"><a href="/"><?= siteT('Home') ?></a><a href="/account.php"><?= siteT('My account') ?></a><a href="/coins.php"><?= siteT('Buy coins') ?></a><a href="/#criar-conta"><?= siteT('Create account') ?></a><a href="/#download"><?= siteT('Download') ?></a></nav><?= siteLanguageSwitcher() ?></div>
<div class="layout"><aside class="sidebar"><h2>Antigas 7.4</h2><a href="/"><?= siteT('Return home') ?></a><a href="/#download"><?= siteT('Download the client') ?></a><div class="side-rule"></div><p><?= siteT('Use the same account number and password as in the game.') ?></p></aside><main class="paper">
<section class="page-title"><h1><?= siteT($account?'Your adventure':'My account') ?></h1><p><?= siteT('Manage your characters in the world of Antigas.') ?></p></section>
<?php if ($message!==''): ?><div class="notice <?= $error?'error':'success' ?>" role="status"><?= e($message) ?></div><?php endif; ?>
<?php if (!$account): ?>
<section class="account-section"><h2><?= siteT('Sign in') ?></h2><form method="post" action="/account.php"><input type="hidden" name="csrf" value="<?= e($_SESSION['csrf']) ?>"><input type="hidden" name="action" value="login"><label for="account"><?= siteT('Account number') ?></label><input id="account" name="account" required inputmode="numeric" maxlength="9" pattern="[1-9][0-9]{0,8}" autocomplete="username"><label for="password"><?= siteT('Password') ?></label><input id="password" name="password" type="password" required maxlength="64" autocomplete="current-password"><button class="button primary"><?= siteT('Sign in to your account') ?></button></form><p><?= siteT('Not playing yet?') ?> <a href="/#criar-conta"><?= siteT('Create your account and first character.') ?></a></p><p class="small-note"><?= siteT('Email recovery is not available yet.') ?></p></section>
<?php else: ?>
<section class="content-section"><h2><?= siteT('Account {id}',['id'=>$account['id']]) ?></h2><p><?= siteT('Premium: {days} days · Points: {points}',['days'=>(int)$account['premdays'],'points'=>(int)$account['premium_points']]) ?></p><form method="post" action="/account.php"><input type="hidden" name="csrf" value="<?= e($_SESSION['csrf']) ?>"><input type="hidden" name="action" value="logout"><button class="button"><?= siteT('Sign out securely') ?></button></form></section>
<section class="content-section"><h2><?= siteT('Your characters') ?></h2><div class="character-list"><?php foreach ($characters as $c): ?><article class="character-card"><h3><?= e($c['name']) ?></h3><p><?= siteT('Level {level} · {vocation}',['level'=>(int)$c['level'],'vocation'=>[0=>'No vocation',1=>'Sorcerer',2=>'Druid',3=>'Paladin',4=>'Knight',5=>'Master Sorcerer',6=>'Elder Druid',7=>'Royal Paladin',8=>'Elite Knight'][(int)$c['vocation']]??siteTranslation('Adventurer')]) ?></p></article><?php endforeach; ?></div></section>
<section class="account-section"><h2><?= siteT('A new adventurer') ?></h2><p><?= siteT('Level 1 in Rookgaard. Your starting kit is delivered by the server on your first login.') ?></p><form method="post" action="/account.php"><input type="hidden" name="csrf" value="<?= e($_SESSION['csrf']) ?>"><input type="hidden" name="action" value="character"><label for="name"><?= siteT('Character name') ?></label><input id="name" name="name" required minlength="3" maxlength="25" pattern="[A-Za-z][A-Za-z ]{2,24}"><label for="sex"><?= siteT('Initial appearance') ?></label><select id="sex" name="sex"><option value="1"><?= siteT('Male') ?></option><option value="0"><?= siteT('Female') ?></option></select><button class="button primary"><?= siteT('Create character') ?></button></form></section>
<section class="account-section"><h2><?= siteT('Change password') ?></h2><form method="post" action="/account.php"><input type="hidden" name="csrf" value="<?= e($_SESSION['csrf']) ?>"><input type="hidden" name="action" value="password"><label for="current_password"><?= siteT('Current password') ?></label><input id="current_password" name="current_password" type="password" required maxlength="64" autocomplete="current-password"><label for="new_password"><?= siteT('New password') ?></label><input id="new_password" name="new_password" type="password" required minlength="8" maxlength="64" autocomplete="new-password"><label for="confirm_password"><?= siteT('Confirm new password') ?></label><input id="confirm_password" name="confirm_password" type="password" required minlength="8" maxlength="64" autocomplete="new-password"><button class="button primary"><?= siteT('Save new password') ?></button></form></section>
<?php endif; ?><footer><?= siteT('Antigas 7.4 · Independent community project.') ?></footer></main></div></body></html>
