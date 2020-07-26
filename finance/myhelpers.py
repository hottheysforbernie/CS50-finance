import os
import requests
import urllib.parse
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from functools import wraps

def updateprice(user, assets, db):
    stocks = db.execute("SELECT symbol FROM transactions WHERE userid=:user AND symbol <> 'CASH'", user=user)
    for stock in stocks:
        sym = stock['symbol']
        lookedup = lookup(sym)
        currentprice = lookedup['price']
        shares = db.execute("SELECT quantity FROM transactions WHERE symbol = :sym AND userid=:user", sym=sym, user=user)
        share = int(shares[0]['quantity'])
        total = share * currentprice
        assets += total
        db.execute("UPDATE transactions SET value = :value WHERE userid=:user AND symbol=:sym", value=usd(currentprice), user=user, sym=sym)
        db.execute("UPDATE transactions SET total = :total WHERE userid=:user AND symbol=:sym", total=usd(total), user=user, sym=sym)
    return assets

def addhistory(buy, user, symbol, quantity, db):
    lookedup = lookup(symbol)
    each = lookedup['price']
    if buy is False:
        quantity = -quantity
    total = quantity * each
    date = datetime.datetime.now()
    db.execute("INSERT INTO history (date, symbol, quantity, each, total, user) VALUES (:date, :symbol, :quantity, :each, :total, :user)",
        date=date, symbol=symbol, quantity=quantity, each=usd(each), total=usd(total), user=user)
