"""Synthetic HHGOA-shaped dataset generator.

This is NOT the HHGOA_IEEE dataset. It produces files with the same *shape* (IEEE-CIS style
columns plus customer_id / timestamp / channel / risk_score, closed cases, a 20-case pack and
policy documents) so the whole pipeline can be built and tested end-to-end before the real
data is available. Column names are mapped through ``schema_map.yaml`` so switching to the real
dataset is a config change.

Injected behaviour:
  documented patterns   CARD_TESTING, CNP_NEW_DEVICE, OUT_OF_REGION, ACCOUNT_TAKEOVER, SHARED_ENTITY_RING
  undocumented pattern  DORMANT_REACTIVATION (labelled "UNCLASSIFIED" in closed cases, not in the docs)
  false positives       legit travel, new phone, big-but-normal purchase
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

START = datetime(2026, 1, 1)
DAYS = 181
HISTORY_END = START + timedelta(days=120)  # months 1-4 -> closed cases

FREE_EMAILS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com"]
ISP_EMAILS = ["comcast.net", "att.net", "verizon.net", "charter.net", "cox.net"]
SHADY_EMAILS = ["anonmail.net", "mail.ru", "protonmail.com", "tempmail.io", "guerrillamail.com"]
OSES = ["Windows 10", "iOS 16.1", "Android 13", "Mac OS X 10_15", "Windows 11", "iOS 17.2", "Android 14"]
BROWSERS = ["chrome 118.0", "safari 16.0", "mobile safari 17.0", "edge 118.0", "firefox 119.0", "samsung browser 22.0"]
SCREENS = ["1920x1080", "2560x1440", "1170x2532", "1080x2400", "1366x768", "1440x900"]
DEVICE_INFOS = ["Windows", "iOS Device", "MacOS", "SM-G991B", "Pixel 7", "moto g(60)", "Trident/7.0"]


@dataclass
class Card:
    card_id: str
    customer_id: str
    card1: int
    card2: float
    card3: int
    card4: str
    card5: float
    card6: str


@dataclass
class Device:
    info: str
    os: str
    browser: str
    screen: str
    dtype: str


@dataclass
class Customer:
    customer_id: str
    home_addr1: int
    addr2: int
    email: str
    amt_mu: float
    amt_sigma: float
    online_ratio: float
    rate: float  # txns per day
    active_hours: tuple[int, int]
    cards: list[Card] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)


class Synth:
    def __init__(self, n_customers: int = 1200, seed: int = 7):
        self.rng = np.random.default_rng(seed)
        random.seed(seed)
        self.n_customers = n_customers
        self.customers: list[Customer] = []
        self.txns: list[dict] = []
        self.ident: list[dict] = []
        self.next_txn = 3_000_000
        self.cases: list[dict] = []
        self.truth: list[dict] = []
        self.episodes: list[dict] = []

    # ------------------------------------------------------------------ world
    def _device(self) -> Device:
        r = self.rng
        dtype = r.choice(["desktop", "mobile"])
        browser = f"{r.choice(BROWSERS)}.{int(r.integers(0, 6000))}"
        screen = f"{r.choice(SCREENS)}" if r.random() < 0.5 else f"{int(r.integers(360, 2560))}x{int(r.integers(640, 1600))}"
        return Device(str(r.choice(DEVICE_INFOS)), str(r.choice(OSES)), browser, screen, str(dtype))

    def build_world(self) -> None:
        r = self.rng
        used_card1: set[int] = set()
        for i in range(self.n_customers):
            cid = f"CUST-{100000 + i}"
            email = str(r.choice(FREE_EMAILS + ISP_EMAILS, p=[0.35, 0.15, 0.1, 0.08, 0.07, 0.05, 0.06, 0.05, 0.03, 0.03, 0.03]))
            cust = Customer(
                customer_id=cid,
                home_addr1=int(r.integers(100, 540)),
                addr2=87,
                email=email,
                amt_mu=float(r.normal(3.9, 0.5)),
                amt_sigma=float(r.uniform(0.5, 0.9)),
                online_ratio=float(r.beta(2, 3)),
                rate=float(r.gamma(2.0, 0.14)),
                active_hours=(int(r.integers(7, 11)), int(r.integers(19, 23))),
            )
            for _ in range(1 if r.random() < 0.7 else 2):
                c1 = int(r.integers(1000, 18400))
                while c1 in used_card1:
                    c1 = int(r.integers(1000, 18400))
                used_card1.add(c1)
                card = Card(
                    card_id=f"CARD-{len(used_card1):06d}",
                    customer_id=cid,
                    card1=c1,
                    card2=float(r.integers(100, 600)),
                    card3=150 if r.random() < 0.9 else 185,
                    card4=str(r.choice(["visa", "mastercard", "american express", "discover"], p=[0.62, 0.3, 0.05, 0.03])),
                    card5=float(r.choice([226, 224, 166, 102, 117, 138])),
                    card6=str(r.choice(["debit", "credit"], p=[0.72, 0.28])),
                )
                cust.cards.append(card)
            cust.devices = [self._device() for _ in range(1 if r.random() < 0.6 else 2)]
            self.customers.append(cust)

    # ------------------------------------------------------------------ txns
    def _add_txn(self, cust: Customer, card: Card, ts: datetime, amt: float, online: bool, *,
                 device: Device | None = None, addr1: int | None = None, p_email: str | None = None,
                 r_email: str | None = None, product: str | None = None, new_device: bool = False,
                 proxy: str | None = None, m_mismatch: bool = False, risk: float | None = None,
                 dist1: float | None = None) -> int:
        r = self.rng
        tid = self.next_txn
        self.next_txn += 1
        product = product or (str(r.choice(["W", "C", "R", "H", "S"], p=[0.55, 0.15, 0.1, 0.12, 0.08])) if online else "W")
        m = {f"M{i}": "T" for i in range(1, 10)}
        m["M4"] = str(r.choice(["M0", "M1", "M2"], p=[0.6, 0.3, 0.1]))
        if r.random() < 0.08:
            m[f"M{int(r.integers(5, 10))}"] = "F"
        if m_mismatch:
            m["M5"] = "F"
            m["M6"] = "F"
            m["M4"] = "M2"
            m["M3"] = "F"
        home = addr1 is None or addr1 == cust.home_addr1
        row = {
            "TransactionID": tid,
            "customer_id": cust.customer_id,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "TransactionDT": int((ts - START).total_seconds()) + 86400,
            "TransactionAmt": round(float(amt), 2),
            "ProductCD": product,
            "channel": "ONLINE" if online else "CARD_PRESENT",
            "card1": card.card1,
            "card2": card.card2,
            "card3": card.card3,
            "card4": card.card4,
            "card5": card.card5,
            "card6": card.card6,
            "addr1": addr1 if addr1 is not None else cust.home_addr1,
            "addr2": cust.addr2,
            "dist1": dist1 if dist1 is not None else (round(float(r.exponential(8)), 1) if home else round(float(r.uniform(300, 2500)), 1)),
            "P_emaildomain": p_email if p_email is not None else (cust.email if online or r.random() < 0.5 else None),
            "R_emaildomain": r_email if r_email is not None else (cust.email if online and r.random() < 0.3 else None),
            **{f"C{i}": int(r.poisson(1.5)) + (1 if i in (1, 2) else 0) for i in range(1, 15)},
            "D1": int(r.integers(0, 600)),
            "D10": int(r.integers(0, 400)),
            "D15": int(r.integers(0, 500)),
            **m,
            **{f"V{i}": round(float(r.random()), 3) for i in range(1, 6)},
            "risk_score": None,
            "_ep": risk is not None,
        }
        base = r.beta(1.3, 11)
        row["risk_score"] = round(float(risk if risk is not None else base), 4)
        self.txns.append(row)
        if online:
            dev = device or cust.devices[0]
            self.ident.append({
                "TransactionID": tid,
                "id_01": float(r.choice([0.0, -5.0, -10.0, -20.0])),
                "id_02": round(float(r.uniform(1000, 500000)), 1),
                "id_12": "NotFound" if new_device else "Found",
                "id_15": "New" if new_device else "Found",
                "id_23": proxy,
                "id_30": dev.os,
                "id_31": dev.browser,
                "id_33": dev.screen,
                "id_35": "T",
                "id_38": "F" if new_device else "T",
                "DeviceType": dev.dtype,
                "DeviceInfo": dev.info,
            })
        return tid

    def normal_activity(self) -> None:
        r = self.rng
        for cust in self.customers:
            n = int(r.poisson(cust.rate * DAYS))
            days = np.sort(r.integers(0, DAYS, size=n))
            for d in days:
                h = int(r.integers(cust.active_hours[0], cust.active_hours[1] + 1))
                ts = START + timedelta(days=int(d), hours=h, minutes=int(r.integers(0, 60)), seconds=int(r.integers(0, 60)))
                amt = math.exp(r.normal(cust.amt_mu, cust.amt_sigma))
                online = r.random() < cust.online_ratio
                card = cust.cards[int(r.integers(0, len(cust.cards)))]
                dev = cust.devices[int(r.integers(0, len(cust.devices)))]
                self._add_txn(cust, card, ts, amt, online, device=dev)

    # ---------------------------------------------------------------- episodes
    def _pick(self) -> tuple[Customer, Card]:
        cust = self.customers[int(self.rng.integers(0, len(self.customers)))]
        return cust, cust.cards[0]

    def _t(self, lo: int, hi: int) -> datetime:
        r = self.rng
        return START + timedelta(days=int(r.integers(lo, hi)), hours=int(r.integers(0, 24)), minutes=int(r.integers(0, 60)))

    def _risk(self, fraud: bool) -> float:
        r = self.rng
        if fraud:
            return float(r.beta(5, 2.6)) if r.random() < 0.8 else float(r.beta(2, 6))  # some fraud scores low
        return float(r.beta(4, 3))  # legit-but-alerted: often high

    def ep_card_testing(self, lo: int, hi: int) -> dict:
        r = self.rng
        cust, card = self._pick()
        t = self._t(lo, hi)
        dev = self._device()
        proxy = "IP_PROXY:ANONYMOUS" if r.random() < 0.5 else None
        ids = []
        k = int(r.integers(3, 7))
        for i in range(k):
            ids.append(self._add_txn(cust, card, t + timedelta(minutes=int(i * r.integers(3, 12))), float(r.uniform(0.99, 9.99)), True,
                                     device=dev, new_device=True, proxy=proxy, product="W", risk=float(r.beta(2, 5))))
        big_t = t + timedelta(minutes=int(k * 10 + r.integers(2, 20)))
        big_amt = float(r.uniform(60, 900))
        trig = self._add_txn(cust, card, big_t, big_amt, True, device=dev, new_device=True, proxy=proxy, product="C", risk=self._risk(True))
        return dict(pattern="CARD_TESTING", fraud=True, cust=cust, card=card, trigger=trig, involved=ids + [trig], t=big_t, amount=big_amt,
                    connected=[])

    def ep_cnp_new_device(self, lo: int, hi: int) -> dict:
        r = self.rng
        cust, card = self._pick()
        t = self._t(lo, hi)
        dev = self._device()
        proxy = "IP_PROXY:ANONYMOUS" if r.random() < 0.6 else None
        ids = []
        for i in range(int(r.integers(1, 4))):
            ids.append(self._add_txn(cust, card, t + timedelta(hours=float(r.uniform(0, 6))), float(r.uniform(80, 700)), True, device=dev,
                                     new_device=True, proxy=proxy, product=str(r.choice(["W", "C"])), risk=self._risk(True)))
        return dict(pattern="CNP_NEW_DEVICE", fraud=True, cust=cust, card=card, trigger=ids[-1], involved=ids, t=t,
                    amount=self.txns[-1]["TransactionAmt"], connected=[])

    def ep_out_of_region(self, lo: int, hi: int) -> dict:
        r = self.rng
        cust, card = self._pick()
        t = self._t(lo, hi)
        far = int((cust.home_addr1 + r.integers(80, 300)) % 540 + 100)
        ids = []
        # home activity continues the same day (the tell)
        home_id = self._add_txn(cust, card, t - timedelta(hours=float(r.uniform(1, 5))), math.exp(r.normal(cust.amt_mu, 0.4)), False)
        for i in range(int(r.integers(1, 4))):
            ids.append(self._add_txn(cust, card, t + timedelta(minutes=int(i * r.integers(10, 60))), float(r.uniform(150, 1400)), False,
                                     addr1=far, risk=self._risk(True), p_email=""))
        return dict(pattern="OUT_OF_REGION", fraud=True, cust=cust, card=card, trigger=ids[-1], involved=ids, t=t,
                    amount=self.txns[-1]["TransactionAmt"], connected=[], extra={"home_txn": home_id})

    def ep_ato(self, lo: int, hi: int) -> dict:
        r = self.rng
        cust, card = self._pick()
        t = self._t(lo, hi)
        dev = self._device()
        new_email = str(r.choice(SHADY_EMAILS + FREE_EMAILS[:2]))
        ids = []
        for i in range(int(r.integers(2, 5))):
            online = i % 2 == 0 or r.random() < 0.5
            ids.append(self._add_txn(cust, card, t + timedelta(hours=float(i * r.uniform(1, 10))), float(r.uniform(200, 1500)), online,
                                     device=dev, new_device=online, p_email=new_email, m_mismatch=True, risk=self._risk(True),
                                     product=str(r.choice(["H", "C", "W"]))))
        return dict(pattern="ACCOUNT_TAKEOVER", fraud=True, cust=cust, card=card, trigger=ids[-1], involved=ids, t=t,
                    amount=self.txns[-1]["TransactionAmt"], connected=[])

    def ep_ring(self, lo: int, hi: int) -> list[dict]:
        r = self.rng
        dev = self._device()
        remail = str(r.choice(SHADY_EMAILS))
        t0 = self._t(lo, hi)
        members = []
        n = int(r.integers(3, 7))
        chosen = [self._pick() for _ in range(n)]
        for j, (cust, card) in enumerate(chosen):
            t = t0 + timedelta(hours=float(r.uniform(0, 96)))
            ids = [self._add_txn(cust, card, t + timedelta(minutes=int(i * 30)), float(r.uniform(100, 800)), True, device=dev, new_device=True,
                                 r_email=remail, p_email=str(r.choice(FREE_EMAILS)), product="C", risk=self._risk(True),
                                 proxy="IP_PROXY:ANONYMOUS" if r.random() < 0.3 else None)
                   for i in range(int(r.integers(1, 3)))]
            members.append(dict(pattern="SHARED_ENTITY_RING", fraud=True, cust=cust, card=card, trigger=ids[-1], involved=ids, t=t,
                                amount=self.txns[-1]["TransactionAmt"]))
        all_cards = [m["card"].card_id for m in members]
        for m in members:
            m["connected"] = [c for c in all_cards if c != m["card"].card_id]
        return members

    def ep_dormant(self, lo: int, hi: int) -> dict:
        """Undocumented pattern: a dormant card suddenly makes high-value night-time purchases from a
        *known* device, no proxy, home region. None of the documented signatures fire."""
        r = self.rng
        # choose a low-activity customer so the dormancy gap is real
        cands = [c for c in self.customers if c.rate < 0.12]
        cust = cands[int(r.integers(0, len(cands)))] if cands else self._pick()[0]
        card = cust.cards[-1]
        day = int(r.integers(lo, hi))
        # wipe this card's activity in the previous 45 days to create dormancy
        start = START + timedelta(days=day - 45)
        end = START + timedelta(days=day)
        self.txns = [x for x in self.txns if x["_ep"] or not (x["card1"] == card.card1 and start <= datetime.strptime(x["timestamp"], "%Y-%m-%d %H:%M:%S") < end)]
        t = START + timedelta(days=day, hours=int(r.integers(1, 4)), minutes=int(r.integers(0, 60)))
        ids = []
        for i in range(int(r.integers(2, 5))):
            ids.append(self._add_txn(cust, card, t + timedelta(minutes=int(i * r.integers(5, 25))), float(r.uniform(450, 1600)), True,
                                     device=cust.devices[0], product="H", risk=float(r.beta(3, 4))))
        return dict(pattern="DORMANT_REACTIVATION", fraud=True, cust=cust, card=card, trigger=ids[-1], involved=ids, t=t,
                    amount=self.txns[-1]["TransactionAmt"], connected=[])

    def ep_legit(self, lo: int, hi: int, kind: str | None = None) -> dict:
        r = self.rng
        cust, card = self._pick()
        t = self._t(lo, hi)
        kind = kind or str(r.choice(["TRAVEL", "NEW_PHONE", "BIG_PURCHASE"]))
        if kind == "TRAVEL":
            far = int((cust.home_addr1 + r.integers(80, 300)) % 540 + 100)
            # remove same-day home activity: the customer is actually travelling
            day0 = t.replace(hour=0, minute=0, second=0)
            self.txns = [x for x in self.txns if x["_ep"] or not (x["customer_id"] == cust.customer_id and
                                                      day0 - timedelta(days=1) <= datetime.strptime(x["timestamp"], "%Y-%m-%d %H:%M:%S") < day0 + timedelta(days=2))]
            ids = [self._add_txn(cust, card, t + timedelta(hours=i * 3), float(r.uniform(40, 500)), False, addr1=far, risk=self._risk(False))
                   for i in range(int(r.integers(1, 4)))]
        elif kind == "NEW_PHONE":
            dev = self._device()
            cust.devices.append(dev)
            ids = [self._add_txn(cust, card, t, math.exp(r.normal(cust.amt_mu, 0.5)), True, device=dev, new_device=True, risk=self._risk(False))]
        else:
            ids = [self._add_txn(cust, card, t, math.exp(cust.amt_mu + 2.2 * cust.amt_sigma), bool(r.random() < 0.5), risk=self._risk(False))]
        return dict(pattern=f"LEGIT_{kind}", fraud=False, cust=cust, card=card, trigger=ids[-1], involved=ids, t=t,
                    amount=self.txns[-1]["TransactionAmt"], connected=[])

    # --------------------------------------------------------------- evidence
    def evidence_outcomes(self, ep: dict) -> dict:
        r = self.rng
        pat = ep["pattern"]
        if ep["fraud"]:
            cv = str(r.choice(["DENIED", "NO_REPLY", "CONFIRMED"], p=[0.72, 0.24, 0.04]))
            su = str(r.choice(["FAILED", "PASSED"], p=[0.4, 0.6] if pat == "ACCOUNT_TAKEOVER" else [0.8, 0.2]))
        else:
            cv = str(r.choice(["CONFIRMED", "NO_REPLY", "DENIED"], p=[0.82, 0.15, 0.03]))
            su = str(r.choice(["PASSED", "FAILED"], p=[0.93, 0.07]))
        return {"CUSTOMER_VALIDATION": cv, "STEP_UP_AUTH": su}

    # ------------------------------------------------------------------ cases
    NARR = {
        "CARD_TESTING": "Series of {n} low-value online authorisations on card {card} within an hour from an unrecognised device{proxy}, followed by a {amt} purchase. Consistent with card testing. Customer {cv}.",
        "CNP_NEW_DEVICE": "Card-not-present purchase(s) of {amt} on card {card} from a device never seen on the account{proxy}. Customer {cv}. Confirmed CNP fraud.",
        "OUT_OF_REGION": "Card-present purchases totalling {amt} in region {region} with no prior history while the cardholder continued normal spending at home the same day. Counterfeit card suspected. Customer {cv}.",
        "ACCOUNT_TAKEOVER": "Mixed online and in-store activity on card {card} inconsistent with cardholder profile; new device, changed email domain, address/name match failures. Credentials likely compromised. Step-up {su}.",
        "SHARED_ENTITY_RING": "Card {card} used from a device and recipient email shared with {k} other cards that also showed fraud within days. Linked activity suggests an organised ring.",
        "DORMANT_REACTIVATION": "Card {card} inactive for over six weeks suddenly used for {n} high-value purchases between 1am and 4am. Device matched prior usage. Customer {cv}. Outcome confirmed fraud; pattern did not match documented typologies.",
        "LEGIT_TRAVEL": "Card-present purchases in region {region} flagged as out-of-pattern. No concurrent home activity; customer confirmed travel. Cleared.",
        "LEGIT_NEW_PHONE": "Online purchase from a new device flagged by model. Customer confirmed new phone; step-up {su}. Cleared.",
        "LEGIT_BIG_PURCHASE": "High-value purchase {amt} above usual spend. Known device and region; customer confirmed. Cleared.",
    }
    ACTIONS = {
        "CARD_TESTING": "STEP_UP_AUTH;BLOCK_CARD;CREATE_CASE",
        "CNP_NEW_DEVICE": "CONTACT_CUSTOMER;DECLINE_TRANSACTION;BLOCK_CARD",
        "OUT_OF_REGION": "CONTACT_CUSTOMER;BLOCK_CARD;WARN_CUSTOMER",
        "ACCOUNT_TAKEOVER": "STEP_UP_AUTH;BLOCK_ALL_CARDS;ESCALATE_TO_ANALYST;FILE_REPORT",
        "SHARED_ENTITY_RING": "CREATE_CASE;BLOCK_CARD;FILE_REPORT",
        "DORMANT_REACTIVATION": "CONTACT_CUSTOMER;BLOCK_CARD;ESCALATE_TO_ANALYST",
    }

    def add_case(self, ep: dict, case_id: str, kind: str) -> None:
        r = self.rng
        ev = self.evidence_outcomes(ep)
        pat = ep["pattern"]
        trig_type = str(r.choice(["RISK_SIGNAL", "CUSTOMER_REPORT", "ANALYST_REQUEST"], p=[0.65, 0.23, 0.12]))
        if pat == "SHARED_ENTITY_RING" and r.random() < 0.5:
            trig_type = "ANALYST_REQUEST"
        trig_row = self._tx_index[ep["trigger"]]
        region = trig_row["addr1"]
        cv_text = {"DENIED": "denied making the transaction", "CONFIRMED": "confirmed the transaction", "NO_REPLY": "did not reply within 24h"}[ev["CUSTOMER_VALIDATION"]]
        narrative = self.NARR[pat].format(n=len(ep["involved"]), card=ep["card"].card_id, amt=f"${ep['amount']:.2f}", region=region,
                                          cv=cv_text, su=ev["STEP_UP_AUTH"].lower(), k=len(ep.get("connected", [])),
                                          proxy=" behind an anonymous proxy" if any(self._proxy.get(i) for i in ep["involved"]) else "")
        if kind == "history":
            outcome = "CONFIRMED_FRAUD" if ep["fraud"] else "CLEARED"
            label = pat if pat in self.ACTIONS and pat != "DORMANT_REACTIVATION" else ("UNCLASSIFIED" if ep["fraud"] else "NOT_FRAUD")
            requested = "STEP_UP_AUTH" if pat in ("CARD_TESTING", "ACCOUNT_TAKEOVER", "LEGIT_NEW_PHONE") else "CUSTOMER_VALIDATION"
            self.cases.append({
                "case_id": case_id,
                "opened_at": ep["t"].strftime("%Y-%m-%d %H:%M:%S"),
                "closed_at": (ep["t"] + timedelta(days=float(r.uniform(1, 12)))).strftime("%Y-%m-%d %H:%M:%S"),
                "trigger_type": trig_type,
                "card_id": ep["card"].card_id,
                "customer_id": ep["cust"].customer_id,
                "trigger_txn_id": ep["trigger"],
                "involved_txn_ids": ";".join(str(i) for i in ep["involved"]),
                "connected_card_ids": ";".join(ep.get("connected", [])),
                "outcome": outcome,
                "fraud_pattern": label,
                "evidence_requested": requested,
                "evidence_result": ev[requested],
                "actions_taken": self.ACTIONS.get(pat, "CLOSE_NO_FRAUD") if ep["fraud"] else "CLOSE_NO_FRAUD;MONITOR_CARD",
                "sar_filed": "Y" if ep["fraud"] and (pat in ("SHARED_ENTITY_RING", "ACCOUNT_TAKEOVER") or ep["amount"] >= 1000) else "N",
                "loss_amount": round(sum(self._tx_index[i]["TransactionAmt"] for i in ep["involved"]), 2) if ep["fraud"] else 0.0,
                "analyst_notes": narrative,
            })
        else:
            report = {
                "RISK_SIGNAL": f"Model alert: risk score {trig_row['risk_score']:.2f} on transaction {ep['trigger']}.",
                "CUSTOMER_REPORT": str(r.choice([
                    "Customer called: 'I got a text about a purchase I don't recognise, please check my card.'",
                    "Customer reports: 'There are charges on my statement I did not make.'",
                    "Customer chat: 'Was my card used today? I got an alert while I was at home.'",
                ])),
                "ANALYST_REQUEST": "Analyst request: review card for linked suspicious activity flagged in daily ring report.",
            }[trig_type]
            self.cases.append({
                "case_id": case_id,
                "trigger_type": trig_type,
                "trigger_time": ep["t"].strftime("%Y-%m-%d %H:%M:%S"),
                "card_id": ep["card"].card_id,
                "customer_id": ep["cust"].customer_id,
                "trigger_txn_id": ep["trigger"],
                "risk_score": trig_row["risk_score"],
                "trigger_detail": report,
            })
            self.truth.append({"case_id": case_id, "pattern": pat, "fraud": ep["fraud"],
                               "customer_validation_response": ev["CUSTOMER_VALIDATION"], "step_up_response": ev["STEP_UP_AUTH"]})

    # ------------------------------------------------------------------- main
    def generate(self, out: Path) -> None:
        out.mkdir(parents=True, exist_ok=True)
        r = self.rng
        self.build_world()
        self.normal_activity()
        hist: list[dict] = []
        gens = [(self.ep_card_testing, 90), (self.ep_cnp_new_device, 110), (self.ep_out_of_region, 70), (self.ep_ato, 60), (self.ep_dormant, 25)]
        for fn, n in gens:
            for _ in range(n):
                hist.append(fn(5, 118))
        for _ in range(14):
            hist.extend(self.ep_ring(5, 110))
        for _ in range(95):
            hist.append(self.ep_legit(5, 118))
        # benchmark (months 5-6)
        bench: list[dict] = []
        plan = [self.ep_card_testing] * 3 + [self.ep_cnp_new_device] * 3 + [self.ep_out_of_region] * 2 + [self.ep_ato] * 2 + [self.ep_dormant] * 2
        for fn in plan:
            bench.append(fn(125, 178))
        ring = self.ep_ring(125, 170)
        bench.extend(ring[:2])
        for k in ["TRAVEL", "NEW_PHONE", "BIG_PURCHASE", "TRAVEL", "NEW_PHONE", "BIG_PURCHASE"]:
            bench.append(self.ep_legit(125, 178, k))
        order = list(r.permutation(len(bench)))
        self._tx_index = {x["TransactionID"]: x for x in self.txns}
        self._proxy = {i["TransactionID"]: i["id_23"] for i in self.ident}
        hist.sort(key=lambda e: e["t"])
        # history cases only if closed before the end of month 4
        for i, ep in enumerate(e for e in hist if e["t"] < HISTORY_END - timedelta(days=2)):
            self.add_case(ep, f"CC-{i + 1:05d}", "history")
        hist_cases = self.cases
        self.cases = []
        for j, idx in enumerate(order[:20]):
            self.add_case(bench[int(idx)], f"HHG-{j + 1:03d}", "bench")
        bench_cases = self.cases

        tx = pd.DataFrame(self.txns).drop(columns=["_ep"]).sort_values("TransactionDT")
        kept = set(tx["TransactionID"])
        self.ident = [i for i in self.ident if i["TransactionID"] in kept]
        tx.to_csv(out / "transactions.csv", index=False)
        pd.DataFrame(self.ident).to_csv(out / "identity.csv", index=False)
        pd.DataFrame(hist_cases).to_csv(out / "closed_cases_history.csv", index=False)
        pd.DataFrame(bench_cases).to_csv(out / "case_pack.csv", index=False)
        # hidden ground truth / evidence oracle for the synthetic set only
        pd.DataFrame(self.truth).to_csv(out / "_synthetic_truth.csv", index=False)
        pd.DataFrame([{k: t[k] for k in ("case_id", "customer_validation_response", "step_up_response")} for t in self.truth]).to_csv(
            out / "evidence_responses.csv", index=False)
        write_docs(out)
        print(json.dumps({"transactions": len(tx), "identity": len(self.ident), "closed_cases": len(hist_cases),
                          "fraud": sum(c["outcome"] == "CONFIRMED_FRAUD" for c in hist_cases), "case_pack": len(bench_cases)}))


def write_docs(out: Path) -> None:
    docs = Path(__file__).parent / "synthetic_docs"
    for f in docs.glob("*.md"):
        (out / f.name).write_text(f.read_text())


if __name__ == "__main__":
    import sys

    Synth().generate(Path(sys.argv[1] if len(sys.argv) > 1 else "data/synthetic"))
