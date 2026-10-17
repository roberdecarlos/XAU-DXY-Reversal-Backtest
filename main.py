from AlgorithmImports import *
from datetime import datetime, timedelta, timezone
import csv


DATA_URL = (
    "https://raw.githubusercontent.com/roberdecarlos/"
    "XAU-DXY-Reversal-Backtest/main/XAUUSD_3m_DXY_H1_closed.csv"
)


class XauDxySignals(PythonData):
    def get_source(self, config, date, is_live_mode):
        return SubscriptionDataSource(
            DATA_URL,
            SubscriptionTransportMedium.REMOTE_FILE,
            FileFormat.CSV,
        )

    def reader(self, config, line, date, is_live_mode):
        if not line or line.startswith("time,"):
            return None

        row = next(csv.reader([line]))
        if len(row) < 7:
            return None

        timestamp = int(row[0])
        bar_time = datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)

        data = XauDxySignals()
        data.symbol = config.symbol
        data.time = bar_time
        data.end_time = bar_time + timedelta(minutes=3)
        data.open = float(row[1])
        data.high = float(row[2])
        data.low = float(row[3])
        data.close = float(row[4])
        data.value = data.close
        data.buy_signal = float(row[5] or 0) != 0
        data.sell_signal = float(row[6] or 0) != 0
        return data


class PercentageFeeModel(FeeModel):
    def __init__(self, rate):
        self.rate = rate

    def get_order_fee(self, parameters):
        value = parameters.security.price * abs(parameters.order.quantity) * self.rate
        return OrderFee(CashAmount(value, "USD"))


class XauDxyReversalBacktest(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2026, 9, 13)
        self.set_end_date(2026, 10, 17)
        self.set_cash(5000)
        self.set_time_zone(TimeZones.UTC)

        self.gold = self.add_cfd(
            "XAUUSD", Resolution.MINUTE, Market.OANDA
        ).symbol

        self.signal_symbol = self.add_data(
            XauDxySignals, "XAU_DXY_SIGNALS", Resolution.MINUTE
        ).symbol

        self.order_quantity = 1.0
        self.securities[self.gold].set_fee_model(PercentageFeeModel(0.0002))

        self.buy_signals = 0
        self.sell_signals = 0

    def on_data(self, data: Slice):
        if not data.contains_key(self.signal_symbol):
            return
        signal = data[self.signal_symbol]
        if signal is None or not self.securities[self.gold].has_data:
            return

        quantity = self.portfolio[self.gold].quantity

        if signal.buy_signal and quantity <= 0:
            if quantity < 0:
                self.liquidate(self.gold, "Cerrar venta por senal alcista")
            self.market_order(self.gold, self.order_quantity, tag="Abrir compra")
            self.buy_signals += 1

        elif signal.sell_signal and quantity >= 0:
            if quantity > 0:
                self.liquidate(self.gold, "Cerrar compra por senal bajista")
            self.market_order(self.gold, -self.order_quantity, tag="Abrir venta")
            self.sell_signals += 1

    def on_end_of_algorithm(self):
        self.debug(
            f"Senales procesadas: compras={self.buy_signals}, "
            f"ventas={self.sell_signals}"
        )
