"""Persistent balance baselines; automation owns all downstream actions."""
import asyncio
import hashlib
from decimal import Decimal, InvalidOperation
import time

from sakubot.plugin import object_schema


class BalancePolling:
    def setup_polling(self):
        self.poll_changed = asyncio.Event()
        self.settings_form(self.fields, validate=self.validate_polling, on_saved=self.settings_saved)
        self.trigger_source(
            'balance_low.*', '余额跌至预警值',
            object_schema({'provider_id': {'type': 'string', 'title': '供应商 ID'},
                           'currency': {'type': 'string', 'title': '币种'}}),
            object_schema({'provider_id': {'type': 'string'}, 'provider_name': {'type': 'string'},
                           'currency': {'type': 'string'}, 'previous_balance': {'type': 'string'},
                           'balance': {'type': 'string'}, 'threshold': {'type': 'string'},
                           'fetched_at': {'type': 'string'}},
                          ('provider_id', 'currency', 'previous_balance', 'balance', 'threshold', 'fetched_at')), legacy_ids=('balance_low',))

    def validate_polling(self, values):
        try:
            threshold = Decimal(values['warning_threshold'])
            if not threshold.is_finite() or threshold < 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            raise ValueError('预警值必须为非负金额') from None
        key = values['poll_provider_id']
        if key and not any(p.id == key and self.official(p) for p in self.runtime.config.settings.providers):
            raise ValueError('请选择 DeepSeek 官方供应商 ID，留空查询全部官方供应商')

    def settings_saved(self):
        self.poll_changed.set()

    async def start(self):
        self.background(self.poll_loop())

    async def poll_loop(self):
        # Delay first observation; loading/reloading a plugin never probes credentials.
        deadline = time.monotonic() + self.config['poll_interval_minutes'] * 60
        while True:
            self.poll_changed.clear()
            try:
                await asyncio.wait_for(self.poll_changed.wait(), max(0, deadline - time.monotonic()))
                deadline = time.monotonic() + self.config['poll_interval_minutes'] * 60
                continue
            except asyncio.TimeoutError:
                pass
            if self.config['poll_enabled']:
                snapshot = dict(self.config)
                providers = [p for p in self.runtime.config.settings.providers if self.official(p)
                             and (not snapshot['poll_provider_id'] or p.id == snapshot['poll_provider_id'])]
                for provider in providers:
                    try:
                        result = await self.balance(provider_id=provider.id)
                        # Do not compare an in-flight query against a newly saved rule.
                        if dict(self.config) == snapshot:
                            await self.observe(provider, result, snapshot)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        self.state.set('poll_error:' + provider.id, {'at': time.time(), 'error': str(exc)[:200]})
                        self.runtime.store.log('warning', self.id, 'balance.poll.failed',
                                               data={'provider_id': provider.id, 'error': type(exc).__name__})
            deadline = time.monotonic() + self.config['poll_interval_minutes'] * 60

    async def observe(self, provider, result, config):
        threshold = Decimal(config['warning_threshold'])
        # Key changes (including credentials) establish a fresh baseline without storing secrets.
        account = hashlib.sha256(provider.api_key.encode()).hexdigest()
        signature = [str(threshold), config['poll_provider_id'], account]
        key = 'poll_baseline:' + provider.id
        stored = self.state.get(key, {})
        previous = stored.get('balances', {}) if stored.get('signature') == signature else {}
        current = {}
        for row in result['balance_infos']:
            currency = row['currency']
            balance = Decimal(str(row['total_balance']))
            if not isinstance(currency, str) or not currency or not balance.is_finite():
                raise ValueError('余额或币种无效')
            current[currency] = str(balance)
        for currency, value in current.items():
            if currency in previous and Decimal(previous[currency]) > threshold >= Decimal(value):
                await self.emit_trigger('balance_low.' + provider.id + '.' + currency, {
                    'provider_id': provider.id, 'provider_name': provider.name, 'currency': currency,
                    'previous_balance': previous[currency], 'balance': value,
                    'threshold': str(threshold), 'fetched_at': result['fetched_at'],
                }, uid='balance-low:' + provider.id + ':' + currency + ':' + result['fetched_at'])
        self.state.set(key, {'signature': signature, 'balances': current})
        self.state.set('poll_error:' + provider.id, None)
