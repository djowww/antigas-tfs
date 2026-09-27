<?php
declare(strict_types=1);
require (getenv('ANTIGAS_WEB_LIB')?:'/opt/antigas-web/private').'/security.php';
webStart();
function e(string $v): string { return htmlspecialchars($v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
$message='';$messageType='info';$accountName='';$email='';$characterName='';$sex='1';
$downloadUrl='https://tibia74.tech/Antigas-7.4-Client-v38.zip';
if ($_SERVER['REQUEST_METHOD']==='POST') {
    $accountName=trim(webField('account_name',9));
    $email=trim(webField('email',255));
    $characterName=preg_replace('/ +/',' ',trim(webField('character_name',80)));
    $sex=webField('sex',1);
    $password=webField('password',64);
    $pdo=null;
    try {
        if (webField('website')!=='' || isset($_POST['website']) && !is_string($_POST['website'])) throw new DomainException('Não foi possível concluir o cadastro.');
        if (!hash_equals($_SESSION['csrf'],webField('csrf',64))) throw new DomainException('A sessão do formulário expirou. Atualize a página e tente novamente.');
        if (!webLimit('register:'.($_SERVER['REMOTE_ADDR']??'unknown'),5,3600)) throw new DomainException('Muitas tentativas neste período. Aguarde uma hora e tente novamente.');
        if (!preg_match('/\\A[1-9][0-9]{5,8}\\z/D',$accountName)) throw new DomainException('Escolha um número de conta com 6 a 9 dígitos, sem zero no início.');
        if (!webName($characterName) || !in_array($sex,['0','1'],true)) throw new DomainException('Escolha um nome de 3 a 25 letras e espaços, sem títulos administrativos.');
        if ($email!=='' && !filter_var($email,FILTER_VALIDATE_EMAIL)) throw new DomainException('Informe um e-mail válido ou deixe o campo vazio.');
        if (!webPassword($password)) throw new DomainException('Use uma senha de 8 a 64 caracteres, sem caracteres de controle.');
        if (!hash_equals($password,webField('password_confirm',64))) throw new DomainException('As senhas não coincidem.');
        $pdo=webDb();$pdo->beginTransaction();
        // Account type and player group come from NORMAL database defaults.
        // The web database user cannot insert/update those privilege columns.
        $q=$pdo->prepare('INSERT INTO accounts (id,password,email,created) VALUES (?,?,?,?)');
        $q->execute([(int)$accountName,sha1($password),$email,time()]);
        $q=$pdo->prepare("INSERT INTO players (name,account_id,level,vocation,health,healthmax,conditions,cap,sex,looktype,lookhead,lookbody,looklegs,lookfeet,soul,town_id,posx,posy,posz,comment,created) VALUES (?,?,1,0,150,150,'',400,?,?,78,69,58,76,100,11,32097,32219,7,'',UNIX_TIMESTAMP())");
        $q->execute([$characterName,(int)$accountName,(int)$sex,$sex==='1'?128:136]);
        $pdo->commit();
        $message='Conta '.$accountName.' criada! '.$characterName.' já espera por você em Rookgaard. Entre no cliente com esse número e a senha escolhida.';
        $messageType='success';$accountName='';$email='';$characterName='';
        $_SESSION['csrf']=bin2hex(random_bytes(32));
    } catch (DomainException $ex) {
        if ($pdo && $pdo->inTransaction()) $pdo->rollBack();
        $message=$ex->getMessage();$messageType='error';
    } catch (Throwable $ex) {
        if ($pdo && $pdo->inTransaction()) $pdo->rollBack();
        $message=$ex instanceof PDOException && (string)$ex->getCode()==='23000'?'O número da conta ou o nome do personagem já está em uso.':'O cadastro está temporariamente indisponível.';
        error_log('Antigas registration: '.get_class($ex).' code '.$ex->getCode());
        $messageType='error';
    }
}
?>
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#090b17">
  <meta name="description" content="Entre em um mundo clássico inspirado no Tibia 7.4. Crie sua conta e baixe o cliente.">
  <link rel="canonical" href="https://tibia74.tech/">
  <title>Antigas 7.4 — Uma nova aventura</title>
  <link rel="stylesheet" href="/classic-2004.css?v=20260924-1">
  <link rel="stylesheet" href="/home-improvements.css?v=20260927-2">
  <link rel="stylesheet" href="/news-changelog.css?v=20260927-1">
</head>
<body class="portal-home">
  <a class="skip-link" href="#conteudo">Pular para o conteúdo</a>
  <div class="skyline">
    <header class="masthead">
      <a class="wordmark" href="/" aria-label="Antigas 7.4 — início"><span>Antigas</span><i>7.4 CLASSIC</i></a>
      <p class="motto">Um mundo de aventuras.<br><span>Como nos velhos tempos.</span></p>
    </header>
    <nav class="topnav" aria-label="Navegação principal">
      <a href="#inicio" aria-current="page">Início</a><a href="#noticias">Novidades</a><a href="#mundo">O mundo</a><a href="#market">Market</a><a href="/account.php">Minha conta</a><a href="/coins.php">Comprar coins</a><a href="#criar-conta">Criar conta</a><a href="#download">Download</a>
    </nav>
  </div>

  <div class="layout" id="inicio">
    <aside class="sidebar">
      <nav class="stone-menu" aria-label="Guia do jogador">
        <h2>Guia do jogador</h2>
        <a href="#noticias">Últimas notícias</a>
        <a href="#primeiros-passos">Primeiros passos</a>
        <a href="https://pt.wikipedia.org/wiki/Tibia" target="_blank" rel="noopener noreferrer" aria-label="Tibia na Wikipédia (abre em nova aba)">Wikipédia ↗</a>
        <a href="#sobre">Sobre o Antigas</a>
        <div class="side-rule" aria-hidden="true"></div>
      </nav>
      <p class="side-signature">Antigas<span>7.4</span></p>
      <section class="world-note" aria-labelledby="world-heading">
        <h2 id="world-heading">Nosso mundo</h2>
        <dl><div><dt>Versão</dt><dd>7.4</dd></div><div><dt>Início</dt><dd>Rookgaard</dd></div></dl>
        <p class="world-caption">Velhos caminhos.<br>Novas histórias.</p>
      </section>
      <nav class="side-news" aria-label="Notícias em destaque">
        <h2>No mural</h2>
        <a href="#questlog">Quest Log no cliente<time datetime="2026-09-27">27 set 2026</time></a>
        <a href="#bestiary">Bestiary com progresso<time datetime="2026-09-26">26 set 2026</time></a>
        <a href="#hunt">Hunt e bônus online<time datetime="2026-09-25">25 set 2026</time></a>
        <a href="#market">O Market chegou<time datetime="2026-09-24">24 set 2026</time></a>
        <a href="#mundo">O mundo está aberto<time datetime="2026-09-23">23 set 2026</time></a>
      </nav>
    </aside>

    <main class="paper" id="conteudo" tabindex="-1">
      <section class="welcome" id="boas-vindas" aria-labelledby="welcome-heading">
        <div class="welcome-copy">
          <p class="eyebrow">Tibia 7.4 clássico</p>
          <h1 id="welcome-heading">Sua aventura começa aqui</h1>
          <p class="intro">Reúna seus amigos, explore cavernas e escreva sua história. O mundo de Antigas espera por você, como nos velhos tempos.</p>
          <div class="welcome-actions"><a class="button" href="#criar-conta">Criar conta</a><a class="button button-secondary" href="#download">Baixar cliente</a><a class="button button-secondary" href="https://pt.wikipedia.org/wiki/Tibia" target="_blank" rel="noopener noreferrer" aria-label="Tibia na Wikipédia (abre em nova aba)">Wikipédia ↗</a></div>
          <ol class="journey-steps" aria-label="Como começar"><li><b aria-hidden="true">1</b><a href="#criar-conta">Crie sua conta</a></li><li><b aria-hidden="true">2</b><a href="#download">Baixe o cliente</a></li><li><b aria-hidden="true">3</b><a href="#primeiros-passos">Entre no mundo</a></li></ol>
        </div>
        <div class="welcome-crest" aria-hidden="true"><img src="/classic-assets/crest.svg" width="126" height="142" alt=""><span>7.4 Classic</span></div>
      </section>
      <section class="page-title" id="noticias"><h2>Últimas notícias</h2><p>Sistemas novos e melhorias no mundo Antigas 7.4.</p></section>
      <article id="questlog" class="news-article update-article">
        <h3 class="news-ribbon"><span>Seu diário de aventuras: Quest Log</span><time datetime="2026-09-27">27 set 2026 · Cliente v35</time></h3>
        <div class="news-body">
          <p class="dropcap">As missões agora ficam mais fáceis de acompanhar. Abra <strong>Quests</strong> na lateral do cliente ou use <strong>Ctrl+J</strong> para pesquisar o Quest Log, filtrar missões e consultar as etapas registradas para seu personagem.</p>
          <p>O diário reúne registros de baús do mapa e missões de NPCs. O progresso é individual e atualizado enquanto a janela está aberta. As recompensas continuam sendo conquistadas no mundo, como sempre.</p>
          <p class="news-note">Alguns baús registram apenas a conclusão da missão; o diário mostra somente as etapas que o servidor consegue confirmar.</p>
        </div>
      </article>

      <figure class="systems-illustration">
        <img src="/classic-assets/adventure-systems.svg" width="960" height="290" loading="lazy" alt="Ilustração em estilo clássico: moedas do Market, livro do Bestiary e diário de quests.">
        <figcaption>Novas ferramentas para negociar, conhecer criaturas e acompanhar suas aventuras.</figcaption>
      </figure>

      <article id="bestiary" class="news-article update-article">
        <h3 class="news-ribbon"><span>Conheça seus adversários no Bestiary</span><time datetime="2026-09-26">26 set 2026 · Cliente v32</time></h3>
        <div class="news-body">
          <p class="dropcap">A enciclopédia de criaturas ganhou uma interface renovada, no estilo clássico do Tibia. Consulte informações e loot, pesquise pelo nome e navegue pelos cards sem perder a posição na lista.</p>
          <p>Os abates do seu personagem alimentam o progresso do Bestiary, com filtros para criaturas em andamento e já completadas. A contagem usa o registro existente no servidor e chega a 1.000 kills por criatura.</p>
        </div>
      </article>

      <article id="client-shop" class="news-article update-article">
        <h3 class="news-ribbon"><span>Shop renovada com a identidade Antigas</span><time datetime="2026-09-27">27 set 2026 · Cliente v34</time></h3>
        <div class="news-body">
          <p class="dropcap">A Shop recebeu um cabeçalho com o brasão A do Antigas, listas mais alinhadas e sprites originais preservados. A navegação por categorias, os detalhes dos produtos, o histórico e as confirmações ficaram mais claros.</p>
          <p>O cliente clássico segue evoluindo por versões incrementais, mantendo o visual antigo e sem exigir instalação adicional.</p>
        </div>
      </article>

      <article id="hunt" class="news-article update-article">
        <h3 class="news-ribbon"><span>Hunt: acompanhe sua sessão e progresso</span><time datetime="2026-09-25">25 set 2026 · Cliente v17</time></h3>
        <div class="news-body">
          <p class="dropcap">O painel Hunt concentra experiência, ritmo da sessão, loot coletado e suprimentos consumidos durante a caça. Os contadores são da sessão e servem para acompanhar a aventura.</p>
          <p>O tempo online também rende um bônus acumulativo: a cada hora, <strong>+0,2% de experiência e skills</strong>, até o limite de <strong>5%</strong>. As taxas base de experiência, skills e loot são 1×.</p>
          <p>Os canais foram simplificados para o mundo: World Chat, Trade e Help. A experiência compartilhada do grupo pode ser controlada no próprio cliente; comandos administrativos ficam restritos à equipe.</p>
        </div>
      </article>

      <article id="market" class="news-article">
        <h3 class="news-ribbon"><span>Market: ofertas entre jogadores</span><time datetime="2026-09-24">24 set 2026</time></h3>
        <div class="news-body">
          <p class="dropcap">Encontre itens, compare ofertas e negocie com outros jogadores diretamente pelo cliente. O catálogo tem busca, categorias e filtros para compras e vendas.</p>
          <ul class="gold-list"><li><strong>Gold:</strong> pagamentos consideram gold, platinum e crystal coins, além do saldo depositado no banco.</li><li><strong>Antigas Coin:</strong> moeda separada, identificada em cada oferta.</li><li><strong>Histórico e resgate:</strong> acompanhe ofertas e negociações; use <strong>Collect</strong> para receber. Gold vai para o banco, itens e Antigas Coins seguem para o depot.</li></ul>
          <p>As negociações são registradas e os valores de uma venda ficam reservados ao vendedor até o resgate.</p>
          <p>Também melhoramos o tratamento de operações interrompidas e do acesso simultâneo ao Market, para proteger as trocas entre jogadores.</p>
        </div>
      </article>
      <article id="mundo" class="news-article">
      <h3 class="news-ribbon"><span>O mundo está aberto para novas aventuras</span><time datetime="2026-09-23">23 set 2026</time></h3>
      <section class="content-section" id="primeiros-passos">
        <h4>Comece sua jornada</h4>
        <p>Das ruas de Thais aos túneis de Rookgaard, reencontre um mundo de descobertas. Sem atalhos: uma corda, uma tocha e a curiosidade já são um bom começo.</p>
        <p>Crie sua conta e seu primeiro personagem aqui. Depois, baixe o cliente, extraia o arquivo e abra <strong>Antigas_gl.exe</strong>. O endereço do servidor já vem configurado.</p>
      </section>
      </article>

      <section class="account-section" id="criar-conta">
        <div class="section-heading"><h2>Criar conta</h2><p>Seu primeiro personagem começa em Rookgaard.</p></div>
        <?php if ($message !== ''): ?><div class="notice <?= e($messageType) ?>" role="status"><?= e($message) ?></div><?php endif; ?>
        <form method="post" action="#criar-conta" autocomplete="on">
          <input type="hidden" name="csrf" value="<?= e((string)$_SESSION['csrf']) ?>">
          <div class="trap" aria-hidden="true"><label>Deixe este campo vazio<input name="website" tabindex="-1" autocomplete="off"></label></div>
          <label for="account_name">Número da conta</label>
          <input id="account_name" name="account_name" value="<?= e($accountName) ?>" required minlength="6" maxlength="9" pattern="[1-9][0-9]{5,8}" inputmode="numeric" autocomplete="username" placeholder="Ex.: 734215" aria-describedby="account-help">
          <small id="account-help">Escolha de 6 a 9 dígitos. Você usará esse número para entrar no jogo.</small>
          <label for="character_name">Nome do personagem</label>
          <input id="character_name" name="character_name" value="<?= e($characterName) ?>" required minlength="3" maxlength="25" pattern="[A-Za-z][A-Za-z ]{2,24}" placeholder="Ex.: Darian">
          <label for="sex">Aparência inicial</label>
          <select id="sex" name="sex"><option value="1" <?= $sex === '1' ? 'selected' : '' ?>>Masculina</option><option value="0" <?= $sex === '0' ? 'selected' : '' ?>>Feminina</option></select>
          <label for="email">E-mail <span>(opcional)</span></label>
          <input id="email" name="email" type="email" value="<?= e($email) ?>" maxlength="255" autocomplete="email" placeholder="voce@exemplo.com">
          <label for="password">Senha</label>
          <input id="password" name="password" type="password" required minlength="8" maxlength="64" autocomplete="new-password" aria-describedby="password-help">
          <label for="password_confirm">Confirme a senha</label>
          <input id="password_confirm" name="password_confirm" type="password" required minlength="8" maxlength="64" autocomplete="new-password" aria-describedby="password-help">
          <p class="password-note" id="password-help">Use de 8 a 64 caracteres e uma senha única para este servidor. Não reutilize a senha do seu e-mail ou de outros serviços.</p>
          <button class="button primary" type="submit">Criar conta e personagem</button>
        </form>
      </section>

      <section class="download-section" id="download">
        <div><h2>Cliente clássico</h2><p>Baixe o cliente configurado para este servidor. Não precisa instalar outro programa.</p></div>
        <a class="button download-button" href="<?= e($downloadUrl) ?>">Baixar cliente 7.4</a>
      </section>
      <footer id="sobre">Antigas 7.4 — Projeto comunitário independente, sem vínculo com a CipSoft.<br>Tibia é uma marca de seus respectivos proprietários.</footer>
    </main>
  </div>
</body>
</html>
