# main.py
from datetime import date, datetime
import sqlite3

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.core.window import Window

from kivymd.app import MDApp
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.list import OneLineAvatarIconListItem, IconLeftWidget, IconRightWidget
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton

KV = """
MDScreen:
    md_bg_color: app.theme_cls.backgroundColor

    MDTopAppBar:
        title: "Finanças"
        elevation: 2
        pos_hint: {"top": 1}

    MDTabs:
        id: tabs
        pos_hint: {"top": 0.92}
        height: "92%"

        MDTabsItem:
            title: "Dashboard"

            MDBoxLayout:
                orientation: "vertical"
                padding: dp(14)
                spacing: dp(12)

                MDBoxLayout:
                    orientation: "horizontal"
                    spacing: dp(10)
                    size_hint_y: None
                    height: self.minimum_height

                    MDTextField:
                        id: month_field
                        hint_text: "Mês (AAAA-MM)"
                        text: app.current_month
                        mode: "outlined"
                        size_hint_x: 0.65
                        input_filter: None

                    MDRaisedButton:
                        text: "Atualizar"
                        size_hint_x: 0.35
                        on_release: app.refresh_dashboard()

                MDCard:
                    padding: dp(14)
                    radius: [18, 18, 18, 18]
                    elevation: 1

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(8)

                        MDLabel:
                            id: invoice_label
                            text: "Fechamento da fatura: --"
                            halign: "left"
                            font_style: "BodyMedium"

                        MDSeparator:

                        MDLabel:
                            id: income_label
                            text: "Entradas: R$ 0,00"
                            font_style: "TitleMedium"

                        MDLabel:
                            id: fixed_label
                            text: "Fixos: R$ 0,00"
                            font_style: "BodyLarge"

                        MDLabel:
                            id: extra_label
                            text: "Extras: R$ 0,00"
                            font_style: "BodyLarge"

                        MDLabel:
                            id: daily_label
                            text: "Diários: R$ 0,00"
                            font_style: "BodyLarge"

                        MDSeparator:

                        MDLabel:
                            id: total_label
                            text: "Total de gastos: R$ 0,00"
                            font_style: "TitleMedium"

                        MDLabel:
                            id: balance_label
                            text: "Saldo: R$ 0,00"
                            font_style: "TitleMedium"

                        MDLabel:
                            id: yield_label
                            text: "Rendimento: 0,00%"
                            font_style: "BodyLarge"

                MDBoxLayout:
                    orientation: "horizontal"
                    spacing: dp(10)
                    size_hint_y: None
                    height: dp(52)

                    MDRaisedButton:
                        text: "+ Fixo"
                        on_release: app.open_add_dialog("fixed")

                    MDRaisedButton:
                        text: "+ Extra"
                        on_release: app.open_add_dialog("extra")

                    MDRaisedButton:
                        text: "+ Diário"
                        on_release: app.open_add_dialog("daily")

                    MDRaisedButton:
                        text: "+ Renda"
                        on_release: app.open_add_dialog("income")

                MDCard:
                    padding: dp(12)
                    radius: [18, 18, 18, 18]
                    elevation: 1

                    MDBoxLayout:
                        orientation: "vertical"

                        MDLabel:
                            text: "Lançamentos do mês (toque para apagar)"
                            font_style: "BodyMedium"
                            size_hint_y: None
                            height: self.texture_size[1] + dp(8)

                        ScrollView:
                            MDList:
                                id: tx_list

        MDTabsItem:
            title: "Config"

            MDBoxLayout:
                orientation: "vertical"
                padding: dp(14)
                spacing: dp(12)

                MDCard:
                    padding: dp(14)
                    radius: [18, 18, 18, 18]
                    elevation: 1

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10)

                        MDLabel:
                            text: "Configurações"
                            font_style: "TitleMedium"

                        MDTextField:
                            id: close_day
                            hint_text: "Dia de fechamento da fatura (1-28)"
                            mode: "outlined"
                            input_filter: "int"

                        MDRaisedButton:
                            text: "Salvar"
                            on_release: app.save_settings()

                MDCard:
                    padding: dp(14)
                    radius: [18, 18, 18, 18]
                    elevation: 1

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(8)

                        MDLabel:
                            text: "Dica"
                            font_style: "BodyMedium"
                        MDLabel:
                            text: "Use mês AAAA-MM no Dashboard para ver totais por mês."
                            font_style: "BodySmall"
"""


def money_fmt(v: float) -> str:
    # Formato simples PT-BR
    s = f"{v:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


class FinanceDB:
    def __init__(self, path="finance.db"):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init()

    def _init(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,             -- fixed | extra | daily | income
                title TEXT NOT NULL,
                amount REAL NOT NULL,           -- positivo (income) ou positivo (gasto). vamos tratar pelo kind
                tx_date TEXT NOT NULL,          -- YYYY-MM-DD
                created_at TEXT NOT NULL
            )
        """)
        # defaults
        if self.get_setting("invoice_close_day") is None:
            self.set_setting("invoice_close_day", "10")
        self.conn.commit()

    def get_setting(self, key: str):
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def set_setting(self, key: str, value: str):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        self.conn.commit()

    def add_tx(self, kind: str, title: str, amount: float, tx_date: str):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO transactions(kind, title, amount, tx_date, created_at)
            VALUES(?, ?, ?, ?, ?)
        """, (kind, title, float(amount), tx_date, datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()

    def delete_tx(self, tx_id: int):
        self.conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        self.conn.commit()

    def list_month(self, month_yyyy_mm: str):
        # month_yyyy_mm: "2026-02"
        start = f"{month_yyyy_mm}-01"
        # truque simples: selecionar pelo prefixo YYYY-MM
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, kind, title, amount, tx_date
            FROM transactions
            WHERE substr(tx_date, 1, 7) = ?
            ORDER BY tx_date DESC, id DESC
        """, (month_yyyy_mm,))
        return cur.fetchall()

    def totals_month(self, month_yyyy_mm: str):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT kind, COALESCE(SUM(amount),0)
            FROM transactions
            WHERE substr(tx_date, 1, 7) = ?
            GROUP BY kind
        """, (month_yyyy_mm,))
        data = {k: float(v) for k, v in cur.fetchall()}
        income = data.get("income", 0.0)
        fixed = data.get("fixed", 0.0)
        extra = data.get("extra", 0.0)
        daily = data.get("daily", 0.0)
        expenses = fixed + extra + daily
        balance = income - expenses
        yield_pct = (balance / income * 100.0) if income > 0 else 0.0
        return {
            "income": income,
            "fixed": fixed,
            "extra": extra,
            "daily": daily,
            "expenses": expenses,
            "balance": balance,
            "yield_pct": yield_pct,
        }


class FinanceApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = FinanceDB()
        self.current_month = date.today().strftime("%Y-%m")
        self.add_dialog = None
        self.pending_kind = None

    def build(self):
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Blue"
        # Window.size = (400, 800)  # útil no PC, no Android ignora
        root = Builder.load_string(KV)
        return root

    def on_start(self):
        self.root.ids.close_day.text = self.db.get_setting("invoice_close_day") or "10"
        self.refresh_dashboard()

    def toast(self, msg: str):
        Snackbar(text=msg, duration=1.8).open()

    def save_settings(self):
        txt = (self.root.ids.close_day.text or "").strip()
        try:
            day = int(txt)
            if not (1 <= day <= 28):
                raise ValueError()
        except Exception:
            self.toast("Dia inválido (use 1 a 28).")
            return
        self.db.set_setting("invoice_close_day", str(day))
        self.toast("Configuração salva.")
        self.refresh_dashboard()

    def refresh_dashboard(self):
        month = (self.root.ids.month_field.text or "").strip()
        if len(month) != 7 or month[4] != "-":
            self.toast("Use mês no formato AAAA-MM.")
            return
        self.current_month = month

        close_day = self.db.get_setting("invoice_close_day") or "10"
        self.root.ids.invoice_label.text = f"Fechamento da fatura: dia {close_day}"

        totals = self.db.totals_month(month)
        self.root.ids.income_label.text = f"Entradas: {money_fmt(totals['income'])}"
        self.root.ids.fixed_label.text = f"Fixos: {money_fmt(totals['fixed'])}"
        self.root.ids.extra_label.text = f"Extras: {money_fmt(totals['extra'])}"
        self.root.ids.daily_label.text = f"Diários: {money_fmt(totals['daily'])}"
        self.root.ids.total_label.text = f"Total de gastos: {money_fmt(totals['expenses'])}"
        self.root.ids.balance_label.text = f"Saldo: {money_fmt(totals['balance'])}"
        self.root.ids.yield_label.text = f"Rendimento: {totals['yield_pct']:.2f}%".replace(".", ",")

        # lista
        tx_list = self.root.ids.tx_list
        tx_list.clear_widgets()

        rows = self.db.list_month(month)
        if not rows:
            tx_list.add_widget(OneLineAvatarIconListItem(text="Sem lançamentos neste mês."))
            return

        for tx_id, kind, title, amount, tx_date in rows:
            kind_icon = {
                "fixed": "calendar-sync",
                "extra": "plus-circle-outline",
                "daily": "coffee-outline",
                "income": "cash-plus",
            }.get(kind, "circle-outline")

            prefix = {"income": "+", "fixed": "-", "extra": "-", "daily": "-"}.get(kind, "-")
            line = f"{tx_date} • {title} • {prefix}{money_fmt(amount)}"

            item = OneLineAvatarIconListItem(text=line)
            item.add_widget(IconLeftWidget(icon=kind_icon))

            # botão apagar
            trash = IconRightWidget(icon="trash-can-outline")
            trash.on_release = lambda tx_id=tx_id: self.confirm_delete(tx_id)
            item.add_widget(trash)

            tx_list.add_widget(item)

    def confirm_delete(self, tx_id: int):
        def _do_delete(*_):
            self.db.delete_tx(tx_id)
            self.toast("Lançamento removido.")
            self.refresh_dashboard()
            if self._confirm_dialog:
                self._confirm_dialog.dismiss()

        def _cancel(*_):
            if self._confirm_dialog:
                self._confirm_dialog.dismiss()

        self._confirm_dialog = MDDialog(
            title="Apagar lançamento?",
            text="Isso não pode ser desfeito.",
            buttons=[
                MDFlatButton(text="Cancelar", on_release=_cancel),
                MDFlatButton(text="Apagar", on_release=_do_delete),
            ],
        )
        self._confirm_dialog.open()

    def open_add_dialog(self, kind: str):
        self.pending_kind = kind

        title_hint = {
            "fixed": "Ex: Aluguel, Internet…",
            "extra": "Ex: Presente, Manutenção…",
            "daily": "Ex: Café, Mercado…",
            "income": "Ex: Salário, Freelance…",
        }.get(kind, "Título")

        kind_label = {
            "fixed": "Adicionar gasto FIXO",
            "extra": "Adicionar gasto EXTRA",
            "daily": "Adicionar gasto DIÁRIO",
            "income": "Adicionar RENDA",
        }.get(kind, "Adicionar")

        # Conteúdo do dialog em KV inline (rápido)
        content = Builder.load_string(f"""
MDBoxLayout:
    orientation: "vertical"
    spacing: dp(10)
    size_hint_y: None
    height: self.minimum_height

    MDTextField:
        id: t_title
        hint_text: "{title_hint}"
        mode: "outlined"

    MDTextField:
        id: t_amount
        hint_text: "Valor (ex: 19.90)"
        mode: "outlined"
        input_filter: None

    MDTextField:
        id: t_date
        hint_text: "Data (AAAA-MM-DD) — vazio = hoje"
        mode: "outlined"
        input_filter: None
""")

        def _save(*_):
            t_title = (content.ids.t_title.text or "").strip()
            t_amount = (content.ids.t_amount.text or "").strip().replace(",", ".")
            t_date = (content.ids.t_date.text or "").strip()

            if not t_title:
                self.toast("Informe um título.")
                return
            try:
                amount = float(t_amount)
                if amount <= 0:
                    raise ValueError()
            except Exception:
                self.toast("Valor inválido.")
                return

            if not t_date:
                t_date = date.today().isoformat()
            else:
                try:
                    datetime.strptime(t_date, "%Y-%m-%d")
                except Exception:
                    self.toast("Data inválida (use AAAA-MM-DD).")
                    return

            self.db.add_tx(kind, t_title, amount, t_date)
            self.toast("Salvo.")
            self.add_dialog.dismiss()
            self.refresh_dashboard()

        def _cancel(*_):
            self.add_dialog.dismiss()

        self.add_dialog = MDDialog(
            title=kind_label,
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=_cancel),
                MDFlatButton(text="Salvar", on_release=_save),
            ],
        )
        self.add_dialog.open()


if __name__ == "__main__":
    FinanceApp().run()