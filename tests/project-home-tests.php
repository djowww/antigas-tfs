<?php
declare(strict_types=1);

if (($argv[1] ?? '') === '--render') {
    $_SERVER['REQUEST_METHOD'] = 'GET';
    $_SERVER['REQUEST_URI'] = $argv[3] === 'index.php' ? '/' : '/wiki.php';
    $_GET['lang'] = $argv[2];
    putenv('ANTIGAS_WEB_LIB=/nonexistent/private-library');
    require ($argv[4] ?? __DIR__ . '/../deploy/site-public') . '/' . $argv[3];
    exit;
}

function renderProjectHome(string $language, string $page, ?string $directory = null): string
{
    $command = escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg(__FILE__)
        . ' --render ' . escapeshellarg($language) . ' ' . escapeshellarg($page)
        . ($directory === null ? '' : ' ' . escapeshellarg($directory));
    exec($command, $lines, $code);
    if ($code !== 0) throw new RuntimeException('The project wiki must render without private libraries or a database.');
    return implode("\n", $lines);
}

function checkHome(bool $condition, string $message): void
{
    if (!$condition) throw new RuntimeException($message);
}

$site = __DIR__ . '/../deploy/site-public';
foreach (['pt' => 'pt-BR', 'en' => 'en', 'es' => 'es', 'pl' => 'pl'] as $language => $tag) {
    foreach (['wiki.php', 'index.php'] as $page) {
        $html = renderProjectHome($language, $page);
        foreach (['wiki-page', '/classic-2004.css', '/wiki.css', 'id="novidades"', 'id="changelog"',
            'id="download"', 'id="guia"', 'Tibia74-Local-Complete.zip', 'local123', 'Local Adventurer',
            'https://github.com/djowww/tibia-7.4-a-classic-rpg-version', 'href="/index.php?jogar=1#download"'] as $required) {
            checkHome(str_contains($html, $required), 'Missing project home content: ' . $required);
        }
        foreach (['getting-started', 'vocations', 'online-bonus', 'combat-pvp', 'spells-runes',
            'quests-bestiary', 'market-coins', 'client-support', 'faq'] as $anchor) {
            checkHome(str_contains($html, 'id="' . $anchor . '"'), 'Existing wiki section lost: ' . $anchor);
        }
        checkHome(str_contains($html, '<html lang="' . $tag . '"'), 'Language selection was lost.');
        checkHome(!str_contains($html, '/blog.css'), 'The separate blog design must not replace the wiki.');
        checkHome(!str_contains($html, 'href="/coins.php"'), 'Payment link reintroduced.');
        checkHome(substr_count($html, 'class="project-update"') === 2, 'Only curated project updates should be published.');
        echo 'PASS project wiki homepage: ' . $page . ' ' . $language . PHP_EOL;
    }
}

// Exercise actual rendering of untrusted editorial text and a tampered source URL.
$fixture = sys_get_temp_dir() . '/project-home-test-' . bin2hex(random_bytes(6));
mkdir($fixture, 0700);
try {
    foreach (['wiki.php', 'i18n.php', 'i18n-extra.php'] as $name) copy($site . '/' . $name, $fixture . '/' . $name);
    $updates = json_decode(file_get_contents($site . '/project-updates.json'), true, 512, JSON_THROW_ON_ERROR);
    $updates[0]['title'] = '<img src=x onerror=alert(1)>';
    $updates[0]['summary'] = '<script>alert(1)</script>';
    $updates[0]['changes'] = ['<b onclick="alert(1)">test</b>'];
    $updates[0]['url'] = 'javascript:alert(1)';
    file_put_contents($fixture . '/project-updates.json', json_encode($updates, JSON_THROW_ON_ERROR));
    $html = renderProjectHome('pt', 'wiki.php', $fixture);
    checkHome(str_contains($html, '&lt;img src=x'), 'News titles must be escaped.');
    checkHome(!str_contains($html, '<script>') && !str_contains($html, '<b onclick='), 'News body markup was executed.');
    checkHome(!str_contains($html, 'href="javascript:'), 'Unsafe project source URL was rendered.');
    echo 'PASS editorial text escaping and source URL restriction' . PHP_EOL;
} finally {
    foreach (glob($fixture . '/*') as $file) unlink($file);
    rmdir($fixture);
}
