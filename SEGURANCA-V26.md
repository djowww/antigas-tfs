# Operação do login a partir da v26

O servidor usa uma chave RSA exclusiva lida do arquivo definido por `ANTIGAS_RSA_KEY_FILE`. No serviço principal, o caminho é `/etc/antigas/login-rsa-v26.key`. A chave privada deve permanecer fora do repositório e dos downloads públicos, com acesso restrito a root e ao usuário do serviço.

O arquivo tem duas linhas decimais, os primos privados P e Q, e não deve ser compartilhado. A chave pública correspondente está no `init.lua` do cliente. Não usar novamente a chave padrão do emulador nem tratar um valor distribuído no cliente como segredo de autenticação.

O protocolo usa blocos RSA de 128 bytes; o carregador verifica a compatibilidade da chave e recusa iniciar se ela estiver ausente ou inválida. A conta e a senha continuam sendo verificadas pelo servidor. O texto `Antigas-26` é somente um marcador público de compatibilidade.

Uma troca futura de chave precisa ser coordenada com a publicação do cliente e o reinício do servidor. Para novos releases sem troca de chave, preservar o módulo público e o marcador de compatibilidade. Rever também os redirecionamentos dos ZIPs antigos no Nginx.

Backups da troca: `/root/backups/security-v26-20260925T210753Z` e `/root/backups/client-v26-20260925T211017Z`. A chave privada precisa integrar o backup protegido de `/etc/antigas`; ela não acompanha esta pasta local.
