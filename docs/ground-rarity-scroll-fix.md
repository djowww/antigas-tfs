# Raridade imediata ao voltar à tela

## Causa

Na versão inicial do servidor v46, o movimento enviava as novas faixas do mapa, mas atualizava a raridade somente nas posições de origem e destino do personagem. As faixas recriam objetos `Item` no cliente. Quando o item continuava com a mesma posição e raridade no cache do servidor, o vínculo com o novo objeto só era recuperado pelo replay periódico de cinco segundos.

O cliente v46 aplica a cor imediatamente quando recebe a descrição correta. A correção é exclusiva do servidor; o ZIP público e a versão do cliente permanecem iguais.

## Correção

- O mesmo trecho que serializa cada faixa nativa registra seu retângulo. Depois de enviar o pacote nativo, o servidor envia os snapshots de raridade correspondentes.
- A geometria reproduz todos os pisos e deslocamentos de perspectiva transmitidos, inclusive movimento diagonal e viewport ampliado. Posições repetidas são deduplicadas.
- Descrições idênticas às do cache também são reenviadas: o objeto no cliente pode ter sido recriado.
- Tiles que saíram da área visível são removidos do cache antes de inserir os novos. Tiles rastreados que passaram a conter somente itens comuns recebem uma descrição vazia.
- Mudanças de andar no protocolo clássico executam reset e sincronização imediatos após os pacotes de piso. Teleportes e mapas completos continuam usando o reset já existente.
- Se o cliente detectar que um objeto nativo do mapa foi recriado sem uma nova descrição, ele pede um snapshot autoritativo do viewport. O servidor limita esse pedido a um replay por jogador a cada cinco segundos.

Os dados da raridade ficam serializados no próprio item. O salvamento das casas percorre os itens móveis dos tiles e chama `Item::serializeAttr`, que grava os atributos de raridade; a cor no mapa é reaplicada a partir desses dados quando o cliente recebe um snapshot. O replay não altera nem recria itens.

A caminhada examina somente as faixas transmitidas: no máximo 400 posições em um passo diagonal com o maior viewport e oito pisos, além das até 256 entradas do cache. O replay periódico continua como recuperação; a entrada normal de tiles na tela não depende dele.

## Validação

As regressões do cliente cobrem cinco raridades, retorno antes e depois da limpeza de referências, recriação de objetos nativos com o mesmo sprite, item comum idêntico, substituição de canto diagonal e reset entre pisos. A execução nativa usa o ZIP v46 publicado, uma cópia isolada e somente transporte dummy localhost.

As regressões C++ exercitam a geometria das faixas e a mesma lógica de cache usada no envio. A ordem entre pacote nativo e metadados também foi revisada nos caminhos de movimento. Os smokes em produção cobrem negociação, reconexão e persistência; não substituem uma sessão visual de caminhada no mundo de produção.

Resultados da correção: `validation/ground-rarity-scroll-fix/`.

Instalação: `deploy/deploy-ground-rarity-scroll-fix.py`. A publicação troca somente o executável, com backup privado do binário e do banco, salvamento normal antes da parada e verificação posterior. Não há migração de dados.

## Publicação em 28/09/2026

- Build Release e núcleo C++ aprovados: **79.076 verificações**, incluindo as 384 combinações de geometria do movimento.
- Cliente: **80 verificações de chão por runtime Lua**, mais regressões de raridade/Loot e demais sistemas; **54 verificações nativas** no ZIP v46 publicado.
- Salvamento e parada limpos às **18:03:23 UTC**; servidor online às **18:04:25 UTC**. A verificação inicial da mensagem de encerramento esperava texto sem espaço e interrompeu a instalação antes da troca. O log confirmou encerramento normal; o verificador foi corrigido para aceitar espaço e a instalação retomada. Nenhum encerramento forçado foi usado.
- Backup privado: `/root/antigas-backups/groundrarity-scroll-20260928T180315Z`.
- Binário: SHA-256 `bbaa5000d7809704672a0533b3c8f9d878262cab26370c47bc7690e080d6915d`.
- Cliente mantido: v46, SHA-256 `5b87c70945a1fbc6cd4228f1d4f4b0f30c6ca2c369c88f3bab28a6ca8b6f2fc4`.
- Smokes de chão, Loot e raridades aprovados em produção, com limpeza dos personagens e itens temporários. O ciclo físico de soltar/recolher foi pulado por falta de tile livre confirmado. A caminhada visual foi coberta pelas fixtures isoladas, sem usar a conta do jogador.
- Site, hash do ZIP v46 e portas públicas 7173/7174 conferidos após a instalação.
