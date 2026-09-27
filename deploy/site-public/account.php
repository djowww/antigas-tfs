<?php
declare(strict_types=1);
require (getenv('ANTIGAS_WEB_LIB')?:'/opt/antigas-web/private').'/security.php';
webStart();
function e($value): string { return htmlspecialchars((string)$value,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
function field(string $name): string { return webField($name); }
function limitAttempt(string $key,int $limit): bool { return webLimit($key,$limit); }
$message=''; $error=false; $account=null; $characters=[]; $pdo=null;
try {
    $pdo=webDb();
    $account=webAccount($pdo);
    if ($_SERVER['REQUEST_METHOD']==='POST') {
        if (!hash_equals($_SESSION['csrf'],field('csrf'))) throw new DomainException('Formulário expirado. Atualize a página.');
        $action=field('action');
        if ($action==='logout') {
            $_SESSION=[]; session_regenerate_id(true); $_SESSION['csrf']=bin2hex(random_bytes(32));
            header('Location: /account.php',true,303); exit;
        }
        $ip=(string)($_SERVER['REMOTE_ADDR']??'unknown');
        if (!limitAttempt('ip:'.$ip,30)) throw new DomainException('Muitas tentativas. Aguarde 15 minutos.');
        if ($action==='login') {
            $id=trim(field('account')); $password=field('password');
            if (!preg_match('/^[1-9][0-9]{0,8}$/D',$id) || strlen($password)>64) throw new DomainException('Conta ou senha incorreta.');
            if (!limitAttempt('login:'.$id,10)) throw new DomainException('Muitas tentativas. Aguarde 15 minutos.');
            $q=$pdo->prepare('SELECT id,password,premdays,premium_points,blocked FROM accounts WHERE id=?'); $q->execute([$id]); $row=$q->fetch();
            // SHA-1 is required by the existing game server; never store plaintext.
            if (!$row || !hash_equals($row['password'],sha1($password)) || $row['blocked']) throw new DomainException('Conta ou senha incorreta.');
            session_regenerate_id(true); $_SESSION['account_id']=(int)$row['id']; $_SESSION['credential_tag']=hash('sha256',$row['password']); $_SESSION['seen']=time(); $_SESSION['csrf']=bin2hex(random_bytes(32));
            header('Location: /account.php',true,303); exit;
        }
        if (!$account) throw new DomainException('Entre na sua conta para continuar.');
        if ($action==='password') {
            $next=field('new_password');
            if (!hash_equals($account['password'],sha1(field('current_password')))) throw new DomainException('A senha atual está incorreta.');
            if (!webPassword($next) || !hash_equals($next,field('confirm_password'))) throw new DomainException('Use uma senha de 8 a 64 caracteres e confirme o mesmo valor.');
            $q=$pdo->prepare('UPDATE accounts SET password=? WHERE id=? AND password=?'); $q->execute([sha1($next),$account['id'],$account['password']]);
            if ($q->rowCount()===0 && !hash_equals($account['password'],sha1($next))) throw new DomainException('A conta mudou em outra sessão. Entre novamente.');
            $account['password']=sha1($next); $_SESSION['credential_tag']=hash('sha256',$account['password']); session_regenerate_id(true);
            $message='Senha atualizada. Use a nova senha no site e no jogo.';
        } elseif ($action==='character') {
            $name=preg_replace('/ +/',' ',trim(field('name'))); $sex=field('sex');
            if (!webName($name) || !in_array($sex,['0','1'],true)) throw new DomainException('Escolha um nome de 3 a 25 letras, sem títulos administrativos.');
            $pdo->beginTransaction();
            $q=$pdo->prepare('SELECT id,password,blocked FROM accounts WHERE id=? FOR UPDATE'); $q->execute([$account['id']]);
            $locked=$q->fetch();
            if (!$locked || $locked['blocked'] || !hash_equals($account['password'],$locked['password'])) throw new DomainException('A conta mudou em outra sessão. Entre novamente.');
            $q=$pdo->prepare('SELECT COUNT(*) FROM players WHERE account_id=? AND deleted=0'); $q->execute([$account['id']]);
            if ((int)$q->fetchColumn()>=8) throw new DomainException('Limite de 8 personagens por conta.');
            $q=$pdo->prepare("INSERT INTO players (name,account_id,level,vocation,health,healthmax,conditions,cap,sex,looktype,lookhead,lookbody,looklegs,lookfeet,soul,town_id,posx,posy,posz,comment,created) VALUES (?,?,1,0,150,150,'',400,?,?,78,69,58,76,100,11,32097,32219,7,'',UNIX_TIMESTAMP())");
            $q->execute([$name,$account['id'],(int)$sex,$sex==='1'?128:136]); $pdo->commit();
            $message=$name.' criado em Rookgaard, no nível 1 e sem privilégios.';
        } else { throw new DomainException('Ação inválida.'); }
        $_SESSION['csrf']=bin2hex(random_bytes(32));
    }
} catch (DomainException $ex) {
    if ($pdo && $pdo->inTransaction()) $pdo->rollBack(); $message=$ex->getMessage(); $error=true;
} catch (Throwable $ex) {
    if ($pdo && $pdo->inTransaction()) $pdo->rollBack();
    $message=$ex instanceof PDOException && (string)$ex->getCode()==='23000'?'Esse nome de personagem já está em uso.':'O serviço de contas está temporariamente indisponível.';
    error_log('Antigas account manager: '.get_class($ex).' code '.$ex->getCode()); $error=true;
}
if ($account && $pdo) {
    try { $q=$pdo->prepare('SELECT name,level,vocation FROM players WHERE account_id=? AND deleted=0 ORDER BY name'); $q->execute([$account['id']]); $characters=$q->fetchAll(); }
    catch (Throwable $ex) { $message='Não foi possível carregar os personagens.'; $error=true; }
}
?>
<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Minha conta — Antigas 7.4</title><link rel="stylesheet" href="/style.css?v=account1"><link rel="stylesheet" href="/account.css"></head>
<body><div class="skyline"><header class="masthead"><a class="wordmark" href="/"><span>Antigas</span><i>7.4 CLASSIC</i></a><p class="motto">Sua próxima aventura começa aqui.</p></header><nav class="topnav"><a href="/">Início</a><a href="/account.php">Minha conta</a><a href="/coins.php">Comprar coins</a><a href="/#criar-conta">Criar conta</a><a href="/#download">Download</a></nav></div>
<div class="layout"><aside class="sidebar"><h2>Antigas 7.4</h2><a href="/">Voltar ao início</a><a href="/#download">Baixar cliente</a><div class="side-rule"></div><p>Use o mesmo número de conta e a mesma senha do jogo.</p></aside><main class="paper">
<section class="page-title"><h1><?= $account?'Sua jornada':'Minha conta' ?></h1><p>Gerencie seus personagens no mundo Antigas.</p></section>
<?php if ($message!==''): ?><div class="notice <?= $error?'error':'success' ?>" role="status"><?= e($message) ?></div><?php endif; ?>
<?php if (!$account): ?>
<section class="account-section"><h2>Entrar</h2><form method="post" action="/account.php"><input type="hidden" name="csrf" value="<?= e($_SESSION['csrf']) ?>"><input type="hidden" name="action" value="login"><label for="account">Número da conta</label><input id="account" name="account" required inputmode="numeric" maxlength="9" pattern="[1-9][0-9]{0,8}" autocomplete="username"><label for="password">Senha</label><input id="password" name="password" type="password" required maxlength="64" autocomplete="current-password"><button class="button primary">Entrar na minha conta</button></form><p>Ainda não joga? <a href="/#criar-conta">Crie sua conta e seu primeiro personagem.</a></p><p class="small-note">Recuperação por e-mail ainda não está disponível.</p></section>
<?php else: ?>
<section class="content-section"><h2>Conta <?= e($account['id']) ?></h2><p>Premium: <?= (int)$account['premdays'] ?> dias · Pontos: <?= (int)$account['premium_points'] ?></p><form method="post" action="/account.php"><input type="hidden" name="csrf" value="<?= e($_SESSION['csrf']) ?>"><input type="hidden" name="action" value="logout"><button class="button">Sair com segurança</button></form></section>
<section class="content-section"><h2>Seus personagens</h2><div class="character-list"><?php foreach ($characters as $c): ?><article class="character-card"><h3><?= e($c['name']) ?></h3><p>Nível <?= (int)$c['level'] ?> · <?= e([0=>'Sem vocação',1=>'Sorcerer',2=>'Druid',3=>'Paladin',4=>'Knight',5=>'Master Sorcerer',6=>'Elder Druid',7=>'Royal Paladin',8=>'Elite Knight'][(int)$c['vocation']]??'Aventureiro') ?></p></article><?php endforeach; ?></div></section>
<section class="account-section"><h2>Um novo aventureiro</h2><p>Nível 1 em Rookgaard. O kit inicial é entregue pelo servidor no primeiro login.</p><form method="post" action="/account.php"><input type="hidden" name="csrf" value="<?= e($_SESSION['csrf']) ?>"><input type="hidden" name="action" value="character"><label for="name">Nome do personagem</label><input id="name" name="name" required minlength="3" maxlength="25" pattern="[A-Za-z][A-Za-z ]{2,24}"><label for="sex">Aparência inicial</label><select id="sex" name="sex"><option value="1">Masculina</option><option value="0">Feminina</option></select><button class="button primary">Criar personagem</button></form></section>
<section class="account-section"><h2>Trocar senha</h2><form method="post" action="/account.php"><input type="hidden" name="csrf" value="<?= e($_SESSION['csrf']) ?>"><input type="hidden" name="action" value="password"><label for="current_password">Senha atual</label><input id="current_password" name="current_password" type="password" required maxlength="64" autocomplete="current-password"><label for="new_password">Nova senha</label><input id="new_password" name="new_password" type="password" required minlength="8" maxlength="64" autocomplete="new-password"><label for="confirm_password">Confirme a nova senha</label><input id="confirm_password" name="confirm_password" type="password" required minlength="8" maxlength="64" autocomplete="new-password"><button class="button primary">Salvar nova senha</button></form></section>
<?php endif; ?><footer>Antigas 7.4 · Projeto comunitário independente.</footer></main></div></body></html>
