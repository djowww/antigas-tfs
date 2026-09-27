<?php
declare(strict_types=1);
$lib=getenv('ANTIGAS_WEB_LIB')?:'/opt/antigas-web/private';require $lib.'/security.php';require $lib.'/pix.php';webStart();
function e($s): string {return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function brl(int $n): string {return 'R$ '.number_format($n/100,2,',','.');}
$account=null;$chars=[];$orders=[];$selected=null;$message='';$quote=null;
try {
    $db=webDb();$account=webAccount($db);
    if($account) {
        $q=$db->prepare('SELECT id,name FROM players WHERE account_id=? AND deleted=0 ORDER BY name');$q->execute([$account['id']]);$chars=$q->fetchAll();
        if($_SERVER['REQUEST_METHOD']==='POST') {
            if(!hash_equals($_SESSION['csrf'],webField('csrf',64)))throw new DomainException('Formulário expirado. Atualize a página.');
            if(!webLimit('pix:'.$account['id'],20,3600) || !webLimit('pix-ip:'.($_SERVER['REMOTE_ADDR']??'unknown'),40,3600))throw new DomainException('Muitas tentativas. Aguarde uma hora.');
            if(!ctype_digit(webField('coins',5)) || !ctype_digit(webField('character',10)))throw new DomainException('Quantidade ou personagem inválido.');
            $id=pixOrder($db,(int)$account['id'],(int)webField('character',10),(int)webField('coins',5),webField('nonce',32),pixQuote());
            header('Location: /coins.php?order='.$id,true,303);exit;
        }
        $id=$_GET['order']??null;
        if($id!==null) {
            if(!is_string($id) || !preg_match('/\A[a-f0-9]{32}\z/D',$id)){http_response_code(404);throw new DomainException('Pedido não encontrado.');}
            $q=$db->prepare('SELECT o.*,p.name FROM coin_orders o LEFT JOIN players p ON p.id=o.character_id WHERE public_id=? AND o.account_id=?');$q->execute([$id,$account['id']]);$selected=$q->fetch();
            if(!$selected){http_response_code(404);throw new DomainException('Pedido não encontrado.');}
            if(isset($_GET['qr'])) {
                if($selected['status']!=='pending'){http_response_code(410);exit;}
                $png=pixQr($selected['payload']);header('Content-Type: image/png');header('Content-Length: '.strlen($png));echo $png;exit;
            }
        }
        $q=$db->prepare('SELECT public_id,coins,brl_cents,status,created_at FROM coin_orders WHERE account_id=? ORDER BY id DESC LIMIT 20');$q->execute([$account['id']]);$orders=$q->fetchAll();
    } elseif(isset($_GET['qr'])) {http_response_code(401);exit;}
    try {$quote=pixQuote();}catch(DomainException $ex){$message=$ex->getMessage();}
}catch(DomainException $ex){$message=$ex->getMessage();}
catch(Throwable $ex){error_log('Antigas Pix: '.get_class($ex).' code '.$ex->getCode());http_response_code(503);$message='O serviço de coins está temporariamente indisponível.';}
$nonce=bin2hex(random_bytes(16));
?>
<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Antigas Coins — Entr. Jogos</title><link rel="stylesheet" href="/classic-2004.css?v=20260924-1"><link rel="stylesheet" href="/coins.css"></head>
<body><div class="skyline"><header class="masthead"><a class="wordmark" href="/"><span>Antigas</span><i>7.4 CLASSIC</i></a><p class="motto">Sua próxima aventura começa aqui.</p></header><nav class="topnav"><a href="/">Início</a><a href="/account.php">Minha conta</a><a href="/coins.php" aria-current="page">Antigas Coins</a><a href="/#download">Download</a></nav></div>
<div class="layout"><aside class="sidebar"><nav class="stone-menu"><h2>Entr. Jogos</h2><a href="/">Voltar ao início</a><a href="/account.php">Minha conta</a><a href="/#market">Conheça o Market</a></nav><p class="side-signature">Antigas<span>7.4</span></p></aside><main class="paper">
<section class="page-title"><h1>Antigas Coins</h1><p>Pix em reais · Aprovação manual · Entrega pelo Market</p></section>
<p class="coin-intro">10 Antigas Coins = US$ 1. O valor em reais é calculado pela última PTAX de venda disponível e fica fixo no seu pedido.</p>
<?php if($message):?><div class="notice error" role="status"><?=e($message)?></div><?php endif;?>
<?php if(!$account):?><section class="coin-panel"><h2>Entre para comprar</h2><p>O pedido fica vinculado à sua conta e ao personagem escolhido.</p><a class="button primary" href="/account.php">Entrar na minha conta</a></section>
<?php elseif($selected):?><section class="coin-panel"><h2>Seu pedido · <?=e($selected['coins'])?> coins</h2><dl class="order-details"><div><dt>Personagem</dt><dd><?=e($selected['name']??$selected['character_id'])?></dd></div><div><dt>Total fixo</dt><dd class="coin-price"><?=brl((int)$selected['brl_cents'])?></dd></div><div><dt>Cotação utilizada</dt><dd>US$ 1 = R$ <?=number_format((int)$selected['rate4']/10000,4,',','.')?> · PTAX de <?=e($selected['rate_date'])?></dd></div></dl>
<?php if($selected['status']==='approved'):?><div class="notice success">Pagamento aprovado. Entre com o personagem escolhido e clique em Market → Collect depot para receber as coins no depósito da cidade natal do personagem.</div>
<?php else:?><div class="pix-grid"><div><img class="pix-qr" src="/coins.php?order=<?=e($selected['public_id'])?>&amp;qr=1" alt="QR Code Pix do pedido, no valor de <?=e(brl((int)$selected['brl_cents']))?>"><p class="small-note">Pague apenas uma vez. A liberação não é instantânea.</p></div><div><h3>Entr. Jogos</h3><p>Recebedor bancário: <strong>Ricardo Zordan</strong><br>Imbituba, SC<br>Chave: <?=e(PIX_KEY)?></p><p>Confira nome e valor no aplicativo do banco antes de confirmar.</p><label for="pix-code">Pix copia e cola</label><textarea id="pix-code" readonly rows="5"><?=e($selected['payload'])?></textarea><p class="small-note">Selecione e copie o código acima. Aguarde a conferência manual do extrato. Gerar este QR Code não confirma pagamento.</p></div></div><?php endif;?>
<p class="small-note">Referência: <?=e($selected['txid'])?><br>Pedido: <?=e($selected['public_id'])?>. Guarde o comprovante e seu número de pedido. Se já pagou, não faça outro pagamento: aguarde a conferência.</p><a href="/coins.php">Voltar aos meus pedidos</a></section>
<?php endif;?>
<?php if($account && !$selected && $quote):?><section class="coin-panel"><h2>Criar pedido</h2><p>PTAX venda de <?=e($quote['date'])?>: US$ 1 = R$ <?=number_format($quote['rate4']/10000,4,',','.')?>. Atualizada automaticamente; não é uma cotação em tempo real.</p><form method="post" action="/coins.php"><input type="hidden" name="csrf" value="<?=e($_SESSION['csrf'])?>"><input type="hidden" name="nonce" value="<?=e($nonce)?>"><label for="character">Personagem que receberá as coins</label><select id="character" name="character" required><?php foreach($chars as $c):?><option value="<?=(int)$c['id']?>"><?=e($c['name'])?></option><?php endforeach;?></select><label for="coins">Quantidade de coins</label><select id="coins" name="coins"><?php foreach([10,50,100,250,500,1000,2500,5000,10000] as $n):?><option value="<?=$n?>"><?=$n?> coins — <?=brl(intdiv($n*10*$quote['rate4']+5000,10000))?></option><?php endforeach;?></select><button class="button primary"<?=!$chars?' disabled':''?>>Gerar pedido e QR Code Pix</button><p class="small-note">Criar um pedido não debita sua conta bancária. O valor definitivo será mostrado no QR Code. Coins são itens do jogo; não se confundem com o saldo de pontos da Shop.</p></form></section><?php endif;?>
<?php if($account && $orders && !$selected):?><section class="coin-panel"><h2>Meus pedidos</h2><div class="orders"><?php foreach($orders as $o):?><a href="/coins.php?order=<?=e($o['public_id'])?>"><strong><?=(int)$o['coins']?> coins · <?=brl((int)$o['brl_cents'])?></strong><span><?=$o['status']==='approved'?'Aprovado · retirar no Market':'Aguardando conferência'?></span><small><?=e($o['created_at'])?> UTC</small></a><?php endforeach;?></div></section><?php endif;?>
<section class="coin-panel"><h2>Como você recebe</h2><ol><li>Escolha seu personagem e gere o pedido.</li><li>Pague o valor exato no Pix, conferindo o recebedor.</li><li>Aguarde a aprovação manual de Entr. Jogos.</li><li>No jogo, abra Market e clique em Collect depot. As coins irão para seu depósito da cidade natal; se estiver cheio, libere espaço e tente novamente.</li></ol><p>Não compartilhe sua senha. Nenhum comprovante enviado pelo jogador libera coins automaticamente.</p></section><footer>Entr. Jogos · Antigas 7.4 · Projeto comunitário independente.</footer></main></div></body></html>
