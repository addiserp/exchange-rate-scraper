// AddisERP — Exchange Rate page behaviour
document.addEventListener('DOMContentLoaded', function () {
  var tbody = document.getElementById('rate-tbody');
  var updatedEl = document.getElementById('rate-updated');
  var refreshBtn = document.getElementById('rate-refresh');
  var statusEl = document.getElementById('rate-status');
  var liveCountEl = document.getElementById('rate-live-count');
  var sortSelect = document.getElementById('rate-sort');
  var bureauTbody = document.getElementById('bureau-tbody');
  var bureauSort = document.getElementById('bureau-sort');
  var bureauCountEl = document.getElementById('bureau-live-count');
  var blackMarketRatesEl = document.getElementById('black-market-rates');

  if (!tbody) return;

  var shareText = '';
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

  // Best-rate comparison: black market vs best private bureau vs best bank.
  // USD Buy = what they pay you per USD (highest is best); USD Sell = what
  // they charge you per USD (lowest is best). The black market is a single
  // live rate, so it appears on both rows.
  // Black market publishes one rate: that is the Buy; Sell = Buy + this spread.
  var BM_SELL_SPREAD = 3;

  function bestOf(list, field, wantHighest) {
    var best = null;
    (list || []).forEach(function (x) {
      if (x.status !== 'ok' || !x.usd || typeof x.usd[field] !== 'number') return;
      if (!best || (wantHighest ? x.usd[field] > best.usd[field] : x.usd[field] < best.usd[field])) best = x;
    });
    return best;
  }

  function renderBlackMarket(data) {
    if (!blackMarketRatesEl) return;
    var bm = data.black_market;
    var bmOk = bm && bm.status === 'ok' && bm.rate != null;
    // Comparison covers licensed channels only (banks + private bureaus).
    var cols = [
      { title: 'Private bureaus (best)', list: data.forex_bureaus },
      { title: 'Banks (best)', list: data.banks }
    ];
    var rows = [
      { label: 'USD Buy', sub: 'highest is best', field: 'buy', high: true },
      { label: 'USD Sell', sub: 'lowest is best', field: 'sell', high: false }
    ];
    var g = document.createElement('div');
    g.className = 'bmc-grid';
    function cell(cls, html) {
      var d = document.createElement('div');
      if (cls) d.className = cls;
      d.innerHTML = html;
      g.appendChild(d);
    }
    cell('', '');
    cols.forEach(function (c) { cell('bmc-h', c.title); });
    rows.forEach(function (r) {
      cell('bmc-rowlabel', r.label + '<small>' + r.sub + '</small>');
      cols.forEach(function (c) {
        var best = bestOf(c.list, r.field, r.high);
        if (best) {
          var who = document.createElement('span');
          who.textContent = best.name.replace(/ Forex Bureau$/i, '');
          cell('', '<span class="bmc-v">' + fmt(best.usd[r.field]) + '</span><span class="bmc-who">' + who.innerHTML + '</span>');
        } else {
          cell('', '<span class="bmc-v">—</span><span class="bmc-who">unavailable</span>');
        }
      });
    });
    blackMarketRatesEl.innerHTML = '';
    blackMarketRatesEl.appendChild(g);

    // Black market: reference only, never part of the comparison.
    var ref = document.createElement('div');
    ref.className = 'bmc-ref';
    ref.textContent = bmOk
      ? 'Reference only — black market: Buy ' + fmt(bm.rate) + ' · Sell ≈ ' + fmt(bm.rate + BM_SELL_SPREAD) + ' (estimated)'
      : 'Reference only — black market rate unavailable right now';
    blackMarketRatesEl.appendChild(ref);

    // text for the Share button
    var lines = ["USD/ETB best rates today (addiserp.com/exchange-rate)"];
    var bb = bestOf(data.forex_bureaus, 'buy', true), bs = bestOf(data.forex_bureaus, 'sell', false);
    var kb = bestOf(data.banks, 'buy', true), ks = bestOf(data.banks, 'sell', false);
    if (bb) lines.push('Best bureau buy: ' + fmt(bb.usd.buy) + ' (' + bb.name + ')');
    if (bs) lines.push('Best bureau sell: ' + fmt(bs.usd.sell) + ' (' + bs.name + ')');
    if (kb) lines.push('Best bank buy: ' + fmt(kb.usd.buy) + ' (' + kb.name + ')');
    if (ks) lines.push('Best bank sell: ' + fmt(ks.usd.sell) + ' (' + ks.name + ')');
    shareText = lines.join('\n');
  }

  // Forex bureaus: "Buy" = what the bureau pays you per USD (highest is best
  // if you're selling USD); "Sell" = what it charges you (lowest is best if
  // you're buying USD). Bureaus without a live rate always sort last.
  function renderBureaus(list) {
    if (!bureauTbody) return;
    var mode = bureauSort ? bureauSort.value : 'usd-buy';
    var rows = (list || []).slice();
    function live(b) { return b.status === 'ok' && b.usd; }
    rows.sort(function (a, b) {
      if (mode === 'name') return a.name.localeCompare(b.name);
      var la = live(a), lb = live(b);
      if (la && !lb) return -1;
      if (!la && lb) return 1;
      if (!la && !lb) return a.name.localeCompare(b.name);
      return mode === 'usd-sell' ? a.usd.sell - b.usd.sell : b.usd.buy - a.usd.buy;
    });
    bureauTbody.innerHTML = '';
    var liveN = 0;
    if (!rows.length) {
      bureauTbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--slate);padding:34px 18px;">Forex bureau rates aren\u2019t available yet.</td></tr>';
    }
    rows.forEach(function (b) {
      if (live(b)) liveN++;
      var tr = document.createElement('tr');
      if (!live(b) && b.reason) tr.title = b.reason;
      var nameTd = document.createElement('td');
      nameTd.textContent = b.name;
      tr.appendChild(nameTd);
      var phoneTd = document.createElement('td');
      if (b.phone) {
        var a = document.createElement('a');
        a.href = 'tel:+251' + b.phone.replace(/\D/g, '').replace(/^0/, '');
        a.textContent = b.phone;
        phoneTd.appendChild(a);
      } else {
        phoneTd.textContent = '—';
      }
      tr.appendChild(phoneTd);
      ['buy', 'sell'].forEach(function (k) {
        var td = document.createElement('td');
        td.className = 'num';
        td.textContent = live(b) ? fmt(b.usd[k]) : '—';
        tr.appendChild(td);
      });
      bureauTbody.appendChild(tr);
    });
    if (bureauCountEl) bureauCountEl.textContent = liveN + ' of ' + rows.length + ' bureaus live';
  }

  function render(data) {
    // NBE only deals with banks, not the public — never show or compare it.
    data.banks = (data.banks || []).filter(function (b) { return !/national bank of ethiopia/i.test(b.name); });
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

    renderBureaus(data.forex_bureaus);
    renderBlackMarket(data);
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

  var shareBtn = document.getElementById('rate-share');
  if (shareBtn) {
    shareBtn.addEventListener('click', function () {
      if (!shareText) return;
      if (navigator.share) {
        navigator.share({ text: shareText }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(shareText).then(function () {
          shareBtn.textContent = 'Copied!';
          setTimeout(function () { shareBtn.textContent = "Share today's rates"; }, 1800);
        });
      }
    });
  }

  if (bureauSort) {
    bureauSort.addEventListener('change', function () {
      if (lastData) renderBureaus(lastData.forex_bureaus);
    });
  }

  if (sortSelect) {
    sortSelect.addEventListener('change', function () {
      if (lastData) render(lastData); // re-sort in place, no need to re-fetch
    });
  }
});
