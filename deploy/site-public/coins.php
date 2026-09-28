<?php
declare(strict_types=1);
$lib=getenv('ANTIGAS_WEB_LIB')?:'/opt/antigas-web/private';require $lib.'/security.php';require $lib.'/pix.php';webStart();require __DIR__.'/i18n.php';$language=siteStartI18n();
function e($s): string {return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function brl(int $n): string {return 'R$ '.number_format($n/100,2,',','.');}
$account=null;$chars=[];$orders=[];$selected=null;$message='';$quote=null;
try {
    $db=webDb();$account=webAccount($db);
    if($account) {
        $q=$db->prepare('SELECT id,name FROM players WHERE account_id=? AND deleted=0 ORDER BY name');$q->execute([$account['id']]);$chars=$q->fetchAll();
        if($_SERVER['REQUEST_METHOD']==='POST') {
            if(!hash_equals($_SESSION['csrf'],webField('csrf',64)))throw new DomainException(siteTranslation('Your form has expired. Refresh the page.'));
            if(!webLimit('pix:'.$account['id'],20,3600) || !webLimit('pix-ip:'.($_SERVER['REMOTE_ADDR']??'unknown'),40,3600))throw new DomainException(siteTranslation('Too many attempts. Wait one hour.'));
            if(!ctype_digit(webField('coins',5)) || !ctype_digit(webField('character',10)))throw new DomainException(siteTranslation('Invalid amount or character.'));
            $id=pixOrder($db,(int)$account['id'],(int)webField('character',10),(int)webField('coins',5),webField('nonce',32),pixQuote());
            header('Location: /coins.php?order='.$id,true,303);exit;
        }
        $id=$_GET['order']??null;
        if($id!==null) {
            if(!is_string($id) || !preg_match('/\A[a-f0-9]{32}\z/D',$id)){http_response_code(404);throw new DomainException(siteTranslation('Order not found.'));}
            $q=$db->prepare('SELECT o.*,p.name FROM coin_orders o LEFT JOIN players p ON p.id=o.character_id WHERE public_id=? AND o.account_id=?');$q->execute([$id,$account['id']]);$selected=$q->fetch();
            if(!$selected){http_response_code(404);throw new DomainException(siteTranslation('Order not found.'));}
            if(isset($_GET['qr'])) {
                if($selected['status']!=='pending'){http_response_code(410);exit;}
                $png=pixQr($selected['payload']);header('Content-Type: image/png');header('Content-Length: '.strlen($png));echo $png;exit;
            }
        }
        $q=$db->prepare('SELECT public_id,coins,brl_cents,status,created_at FROM coin_orders WHERE account_id=? ORDER BY id DESC LIMIT 20');$q->execute([$account['id']]);$orders=$q->fetchAll();
    } elseif(isset($_GET['qr'])) {http_response_code(401);exit;}
    try {$quote=pixQuote();}catch(DomainException $ex){$message=$language==='pt'?$ex->getMessage():siteTranslation('The pricing service is temporarily unavailable. Please try again later.');}
}catch(DomainException $ex){$message=$ex->getMessage();}
catch(Throwable $ex){error_log('Antigas Pix: '.get_class($ex).' code '.$ex->getCode());http_response_code(503);$message=siteTranslation('The coin service is temporarily unavailable.');}
$nonce=bin2hex(random_bytes(16));
?>
<!doctype html><html lang="<?= e(siteLanguageTag()) ?>"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title><?= siteT('Antigas Coins — Entr. Jogos') ?></title><link rel="stylesheet" href="/classic-2004.css?v=20260924-1"><link rel="stylesheet" href="/coins.css"><link rel="stylesheet" href="/language.css?v=1"></head>
<body><div class="skyline"><header class="masthead"><a class="wordmark" href="/"><span>Antigas</span><i>7.4 CLASSIC</i></a><p class="motto"><?= siteT('Your next adventure starts here.') ?></p></header><nav class="topnav" aria-label="<?= siteT('Main navigation') ?>"><a href="/"><?= siteT('Home') ?></a><a href="/account.php"><?= siteT('My account') ?></a><a href="/coins.php" aria-current="page"><?= siteT('Antigas Coins') ?></a><a href="/#download"><?= siteT('Download') ?></a></nav><?= siteLanguageSwitcher() ?></div>
<div class="layout"><aside class="sidebar"><nav class="stone-menu"><h2>Entr. Jogos</h2><a href="/"><?= siteT('Return home') ?></a><a href="/account.php"><?= siteT('My account') ?></a><a href="/#market"><?= siteT('Learn about the Market') ?></a></nav><p class="side-signature">Antigas<span>7.4</span></p></aside><main class="paper">
<section class="page-title"><h1><?= siteT('Antigas Coins') ?></h1><p><?= siteT('Pix in BRL · Manual approval · Delivered through the Market') ?></p></section>
<p class="coin-intro"><?= siteT('10 Antigas Coins = US$ 1. The BRL price uses the latest available PTAX sell rate and is fixed when you place an order.') ?></p>
<?php if($message):?><div class="notice error" role="status"><?=e($message)?></div><?php endif;?>
<?php if(!$account):?><section class="coin-panel"><h2><?= siteT('Sign in to buy') ?></h2><p><?= siteT('The order is linked to your account and selected character.') ?></p><a class="button primary" href="/account.php"><?= siteT('Sign in to your account') ?></a></section>
<?php elseif($selected):?><section class="coin-panel"><h2><?= siteT('Order · {coins} coins',['coins'=>e($selected['coins'])]) ?></h2><dl class="order-details"><div><dt><?= siteT('Character') ?></dt><dd><?=e($selected['name']??$selected['character_id'])?></dd></div><div><dt><?= siteT('Fixed total') ?></dt><dd class="coin-price"><?=brl((int)$selected['brl_cents'])?></dd></div><div><dt><?= siteT('Exchange rate used') ?></dt><dd>US$ 1 = R$ <?=number_format((int)$selected['rate4']/10000,4,',','.')?> · PTAX <?=e($selected['rate_date'])?></dd></div></dl>
<?php if($selected['status']==='approved'):?><div class="notice success"><?= siteT('Payment approved. Log into the game with the selected character and click Market → Collect depot to receive the coins in its hometown depot.') ?></div>
<?php else:?><div class="pix-grid"><div><img class="pix-qr" src="/coins.php?order=<?=e($selected['public_id'])?>&amp;qr=1" alt="<?= siteT('Pix QR code for this order, amount {amount}',['amount'=>brl((int)$selected['brl_cents'])]) ?>"><p class="small-note"><?= siteT('Pay only once. Delivery is not instant.') ?></p></div><div><h3>Entr. Jogos</h3><p><?= siteT('Bank recipient') ?>: <strong>Ricardo Zordan</strong><br><?= siteT('Imbituba, SC') ?><br><?= siteT('Pix key') ?>: <?=e(PIX_KEY)?></p><p><?= siteT('Check the recipient name and amount in your banking app before confirming.') ?></p><label for="pix-code"><?= siteT('Pix copy-and-paste code') ?></label><textarea id="pix-code" readonly rows="5"><?=e($selected['payload'])?></textarea><p class="small-note"><?= siteT('Select and copy the code above. Wait for the manual statement check. Generating this QR code does not confirm payment.') ?></p></div></div><?php endif;?>
<p class="small-note"><?= siteT('Reference:') ?> <?=e($selected['txid'])?><br><?= siteT('Order:') ?> <?=e($selected['public_id'])?>. <?= siteT('Keep your receipt and order number. If you have already paid, do not pay again; wait for confirmation.') ?></p><a href="/coins.php"><?= siteT('Back to my orders') ?></a></section>
<?php endif;?>
<?php if($account && !$selected && $quote):?><section class="coin-panel"><h2><?= siteT('Create order') ?></h2><p><?= siteT('PTAX sell rate for {date}: US$ 1 = R$ {rate}. Updated automatically; this is not a real-time quote.',['date'=>$quote['date'],'rate'=>number_format($quote['rate4']/10000,4,',','.')]) ?></p><form method="post" action="/coins.php"><input type="hidden" name="csrf" value="<?=e($_SESSION['csrf'])?>"><input type="hidden" name="nonce" value="<?=e($nonce)?>"><label for="character"><?= siteT('Character to receive the coins') ?></label><select id="character" name="character" required><?php foreach($chars as $c):?><option value="<?=(int)$c['id']?>"><?=e($c['name'])?></option><?php endforeach;?></select><label for="coins"><?= siteT('Amount of coins') ?></label><select id="coins" name="coins"><?php foreach([10,50,100,250,500,1000,2500,5000,10000] as $n):?><option value="<?=$n?>"><?=$n?> coins — <?=brl(intdiv($n*10*$quote['rate4']+5000,10000))?></option><?php endforeach;?></select><button class="button primary"<?=!$chars?' disabled':''?>><?= siteT('Generate order and QR code') ?></button><p class="small-note"><?= siteT('Creating an order does not charge your bank account. The final amount appears in the QR code. Coins are in-game items and are separate from Shop points.') ?></p></form></section><?php endif;?>
<?php if($account && $orders && !$selected):?><section class="coin-panel"><h2><?= siteT('My orders') ?></h2><div class="orders"><?php foreach($orders as $o):?><a href="/coins.php?order=<?=e($o['public_id'])?>"><strong><?=(int)$o['coins']?> coins · <?=brl((int)$o['brl_cents'])?></strong><span><?=siteT($o['status']==='approved'?'Approved · collect in the Market':'Awaiting manual review')?></span><small><?=e($o['created_at'])?> UTC</small></a><?php endforeach;?></div></section><?php endif;?>
<section class="coin-panel"><h2><?= siteT('How delivery works') ?></h2><ol><li><?= siteT('Choose your character and create the order.') ?></li><li><?= siteT('Pay the exact Pix amount and check the recipient.') ?></li><li><?= siteT('Wait for manual approval by Entr. Jogos.') ?></li><li><?= siteT('In the game, open the Market and click Collect depot. Coins go to your hometown depot. If it is full, make room and try again.') ?></li></ol><p><?= siteT('Never share your password. A player-submitted receipt never releases coins automatically.') ?></p></section><footer><?= siteT('Entr. Jogos · Antigas 7.4 · Independent community project.') ?></footer></main></div></body></html>
