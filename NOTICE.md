# Direitos autorais e componentes de terceiros

Este arquivo registra avisos encontrados no código e os limites da identificação de procedência. Ele não substitui os termos de cada componente e não atribui uma licença única a todos os arquivos do repositório.

## Código do servidor

[src/otserv.cpp](src/otserv.cpp), [src/otpch.h](src/otpch.h) e [src/rsa.cpp](src/rsa.cpp), entre outros arquivos do servidor, identificam a base como **Tibia GIMUD Server**, com copyright de **Alejandro Mujica, 2017**. Seus cabeçalhos declaram a **GNU General Public License, versão 2 ou qualquer versão posterior**, e incluem o aviso de ausência de garantia.

Preserve os cabeçalhos de copyright e licença e os demais créditos existentes ao modificar ou redistribuir esses arquivos. A organização do repositório não altera os termos declarados no código.

## Biblioteca JSON Lua

[data/lib/core/json.lua](data/lib/core/json.lua) inclui copyright de **rxi, 2018** e o aviso de licença **MIT**. [deploy/client-current/modules/corelib/json.lua](deploy/client-current/modules/corelib/json.lua) inclui copyright de **rxi, 2019** e o mesmo aviso MIT. Os textos completos estão nos arquivos e precisam acompanhar cópias ou partes substanciais dessas bibliotecas.

## Cliente, conteúdo do jogo e assets

O snapshot do cliente contém arquivos de uma distribuição baseada em OTClient e modificações específicas deste projeto. Preserve os avisos presentes nesses arquivos e consulte os termos da base utilizada ao preparar uma distribuição completa.

A presença de mapas, definições de itens, NPCs, imagens, estilos ou outros assets neste repositório não estabelece, por si só, uma licença de redistribuição para esse conteúdo. Os termos declarados nos cabeçalhos C++ não comprovam direitos sobre todos os assets ou trabalhos de terceiros. Verifique a procedência e os termos aplicáveis a cada componente antes de redistribuí-lo.
