<?php
header('Content-Type: application/json; charset=utf-8');

$action = $_GET['action'] ?? 'status';
$allowed = ['start', 'stop', 'status'];
if (!in_array($action, $allowed, true)) {
  http_response_code(400);
  echo json_encode(['ok' => false, 'error' => 'Invalid action']);
  exit;
}

$baseDir = __DIR__;
$port = 8090;
$python = file_exists('/opt/homebrew/bin/python3') ? '/opt/homebrew/bin/python3' : 'python3';
$pidFile = '/tmp/oscar_wio.pid';
$logFile = '/tmp/oscar_wio.log';

function is_running(string $host, int $port): bool {
  $errno = 0;
  $errstr = '';
  $fp = @fsockopen($host, $port, $errno, $errstr, 0.4);
  if ($fp) {
    fclose($fp);
    return true;
  }
  return false;
}

function is_pid_running(string $pidFile): bool {
  if (!file_exists($pidFile)) {
    return false;
  }
  $pid = trim((string)@file_get_contents($pidFile));
  if ($pid === '' || !ctype_digit($pid)) {
    return false;
  }
  $out = [];
  exec('ps -p ' . escapeshellarg($pid) . ' -o pid=', $out);
  return !empty($out);
}

if ($action === 'status') {
  $running = is_running('localhost', $port) || is_pid_running($pidFile);
  echo json_encode(['ok' => true, 'running' => $running]);
  exit;
}

if ($action === 'start') {
  if (is_running('localhost', $port)) {
    echo json_encode(['ok' => true, 'running' => true, 'message' => 'Already running']);
    exit;
  }

  $cmd = 'cd ' . escapeshellarg($baseDir)
    . ' && PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'
    . ' && ' . escapeshellarg($python) . ' ' . escapeshellarg($baseDir . '/server.py')
    . ' > ' . escapeshellarg($logFile) . ' 2>&1 < /dev/null & echo $! > ' . escapeshellarg($pidFile);
  exec($cmd);
  usleep(700000);

  $running = is_running('localhost', $port);
  if (!$running) {
    $tail = '';
    if (file_exists($logFile)) {
      $tail = trim((string)shell_exec('tail -n 8 ' . escapeshellarg($logFile)));
    }
    http_response_code(500);
    echo json_encode([
      'ok' => false,
      'running' => false,
      'error' => 'Could not start backend.',
      'details' => $tail !== '' ? $tail : 'No log output. Check Apache user permissions.'
    ]);
    exit;
  }

  echo json_encode(['ok' => true, 'running' => true, 'message' => 'Started']);
  exit;
}

if ($action === 'stop') {
  if (file_exists($pidFile)) {
    $pid = trim((string)@file_get_contents($pidFile));
    if ($pid !== '' && ctype_digit($pid)) {
      exec('kill ' . escapeshellarg($pid));
    }
    @unlink($pidFile);
  }
  exec('pkill -f ' . escapeshellarg('python3 server.py'));
  usleep(300000);

  $running = is_running('localhost', $port);
  echo json_encode([
    'ok' => true,
    'running' => $running,
    'message' => $running ? 'Still running' : 'Stopped'
  ]);
  exit;
}
