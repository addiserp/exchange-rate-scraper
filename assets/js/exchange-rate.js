// AddisERP — Exchange Rate page behaviour
document.addEventListener('DOMContentLoaded', function () {
  var tbody = document.getElementById('rate-tbody');
  var updatedEl = document.getElementById('rate-updated');
  var refreshBtn = document.getElementById('rate-refresh');
  var statusEl = document.getElementById('rate-status');
  var liveCountEl = document.getElementById('rate-live-count');

  if (!tbody) return;

  function fmt(n) {
    if (n === null || n === undefined) return '—';
    return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  }

  function renderRow(bank) {
    var tr = document.createElement('tr');
    if (bank.status !== 'ok' && bank.reason) {
      tr.title = bank.reason;
    }

    var nameTd = document.createElement('td');
    nameTd.textContent = bank.name;
    tr.appendChild(nameTd);

    var swiftTd = document.createElement('td');
    swiftTd.textContent = bank.swift || '—';
    tr.appendChild(swiftTd);

    ['usd', 'eur'].forEach(function (cur) {
      var buyTd = document.createElement('td');
      var sellTd = document.createElement('td');
      var data = bank[cur];
      if (bank.status === 'ok' && data) {
        buyTd.textContent = fmt(data.buy);
        sellTd.textContent = fmt(data.sell);
      } else {
        buyTd.textContent = '—';
        sellTd.textContent = '—';
      }
      buyTd.className = 'num';
      sellTd.className = 'num';
      tr.appendChild(buyTd);
      tr.appendChild(sellTd);
    });

    return tr;
  }

  function render(data) {
    tbody.innerHTML = '';
    var liveCount = 0;
    (data.banks || []).forEach(function (bank) {
      if (bank.status === 'ok') liveCount++;
      tbody.appendChild(renderRow(bank));
    });

    if (liveCountEl) {
      liveCountEl.textContent = liveCount + ' of ' + (data.banks || []).length + ' banks live';
    }

    if (updatedEl) {
      var d = new Date(data.fetched_at * 1000);
      var label = d.toLocaleString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
      updatedEl.textContent = (data.from_cache ? 'Rates as of ' : 'Just refreshed — rates as of ') + label;
    }
  }

  function setStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg || '';
    statusEl.style.color = isError ? '#B3432B' : 'var(--slate)';
  }

  function load(forceRefresh) {
    setStatus(forceRefresh ? 'Refreshing rates from each bank…' : 'Loading rates…');
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--slate);padding:34px 18px;">' +
      'Fetching the latest rates from each bank\u2019s website\u2026</td></tr>';

    var url = 'api/exchange-rates.php' + (forceRefresh ? '?refresh=1' : '');
    fetch(url, { cache: 'no-store' })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) {
            var err = new Error(data.error || ('HTTP ' + res.status));
            err.hint = data.hint;
            throw err;
          }
          return data;
        });
      })
      .then(function (data) {
        render(data);
        setStatus('');
      })
      .catch(function (err) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--slate);padding:34px 18px;">' +
          'Couldn\u2019t load live rates right now. Please try again in a moment.</td></tr>';
        setStatus('Error: ' + err.message + (err.hint ? ' — ' + err.hint : ''), true);
        console.error('exchange-rate.js:', err.message, err.hint || '');
      });
  }

  // Load fresh data every time the page loads / is refreshed.
  load(false);

  if (refreshBtn) {
    refreshBtn.addEventListener('click', function () {
      load(true);
    });
  }
});
