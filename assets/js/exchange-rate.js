// AddisERP — Exchange Rate page behaviour
document.addEventListener('DOMContentLoaded', function () {
  var tbody = document.getElementById('rate-tbody');
  var updatedEl = document.getElementById('rate-updated');
  var refreshBtn = document.getElementById('rate-refresh');
  var statusEl = document.getElementById('rate-status');
  var liveCountEl = document.getElementById('rate-live-count');
  var sortSelect = document.getElementById('rate-sort');
  var blackMarketRatesEl = document.getElementById('black-market-rates');

  if (!tbody) return;

  var lastData = null; // kept so changing the sort order doesn't need a re-fetch

  function fmt(n) {
    if (n === null || n === undefined) return '—';
    return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  }

  // Default sort is USD Buy, highest first; the dropdown can switch to
  // USD Sell instead. Banks without a live USD number (status !== 'ok')
  // always sort to the bottom, regardless of sort field.
  function sortBanks(banks, sortMode) {
    var field = sortMode === 'usd-sell' ? 'sell' : 'buy';
    var sorted = banks.slice();
    sorted.sort(function (a, b) {
      var aOk = a.status === 'ok' && a.usd && typeof a.usd[field] === 'number';
      var bOk = b.status === 'ok' && b.usd && typeof b.usd[field] === 'number';
      if (aOk && !bOk) return -1;
      if (!aOk && bOk) return 1;
      if (!aOk && !bOk) return 0;
      return b.usd[field] - a.usd[field]; // highest first
    });
    return sorted;
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

  function renderBlackMarket(blackMarket) {
    if (!blackMarketRatesEl) return;
    if (!blackMarket || blackMarket.status !== 'ok' || blackMarket.rate == null) {
      blackMarketRatesEl.textContent = 'Unavailable right now' +
        (blackMarket && blackMarket.reason ? ' — ' + blackMarket.reason : '.');
      return;
    }
    blackMarketRatesEl.innerHTML = '';

    // Main live rate
    var rateWrap = document.createElement('div');
    var rateLabel = document.createElement('span');
    rateLabel.className = 'bmc-figure-label';
    rateLabel.textContent = 'Live Rate';
    var rateFigure = document.createElement('div');
    rateFigure.className = 'bmc-figure';
    rateFigure.textContent = fmt(blackMarket.rate) + ' ETB';
    rateWrap.appendChild(rateLabel);
    rateWrap.appendChild(rateFigure);
    blackMarketRatesEl.appendChild(rateWrap);

    // 24h range
    if (blackMarket.range_low != null && blackMarket.range_high != null) {
      var rangeWrap = document.createElement('div');
      var rangeLabel = document.createElement('span');
      rangeLabel.className = 'bmc-figure-label';
      rangeLabel.textContent = "Today's Range";
      var rangeFigure = document.createElement('div');
      rangeFigure.className = 'bmc-figure';
      rangeFigure.style.fontSize = '1rem';
      rangeFigure.textContent = fmt(blackMarket.range_low) + ' – ' + fmt(blackMarket.range_high);
      rangeWrap.appendChild(rangeLabel);
      rangeWrap.appendChild(rangeFigure);
      blackMarketRatesEl.appendChild(rangeWrap);
    }

    // Daily % change
    if (blackMarket.daily_change_pct != null) {
      var changeWrap = document.createElement('div');
      var changeLabel = document.createElement('span');
      changeLabel.className = 'bmc-figure-label';
      changeLabel.textContent = 'Daily';
      var changeFigure = document.createElement('div');
      var pct = blackMarket.daily_change_pct;
      changeFigure.className = 'bmc-change ' + (pct >= 0 ? 'up' : 'down');
      changeFigure.textContent = (pct >= 0 ? '▲ +' : '▼ ') + pct.toFixed(2) + '%';
      changeWrap.appendChild(changeLabel);
      changeWrap.appendChild(changeFigure);
      blackMarketRatesEl.appendChild(changeWrap);
    }
  }

  function render(data) {
    lastData = data;
    var sortMode = sortSelect ? sortSelect.value : 'usd-buy';
    var banks = sortBanks(data.banks || [], sortMode);

    tbody.innerHTML = '';
    var liveCount = 0;
    banks.forEach(function (bank) {
      if (bank.status === 'ok') liveCount++;
      tbody.appendChild(renderRow(bank));
    });

    if (liveCountEl) {
      liveCountEl.textContent = liveCount + ' of ' + banks.length + ' banks live';
    }

    if (updatedEl) {
      var d = new Date(data.fetched_at * 1000);
      var label = d.toLocaleString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
      updatedEl.textContent = (data.from_cache ? 'Rates as of ' : 'Just refreshed — rates as of ') + label;
    }

    renderBlackMarket(data.black_market);
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

  if (sortSelect) {
    sortSelect.addEventListener('change', function () {
      if (lastData) render(lastData); // re-sort in place, no need to re-fetch
    });
  }
});
