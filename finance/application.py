import os
import datetime
import math

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from myhelpers import updateprice, addhistory

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")
currentquote = 0

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

@app.route("/")
@login_required
def index():
    current = session["user_id"]
    toorich = False

    #get current cash amount, start calculating total wealth
    assets = 0
    userinfo = db.execute("SELECT * FROM users WHERE id = :user", user=current)
    cash = userinfo[0]['cash']
    assets += cash

    # get current prices updated
    assets = updateprice(current, assets, db)
    rows = db.execute("SELECT * FROM transactions WHERE userid = :user", user=current)
    if assets >= 1000000:
        toorich = True
    return render_template("index.html", cash=usd(cash), rows=rows, assets=usd(assets), toorich=toorich)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == 'POST':
        if not request.form.get("quantity"):
            return apology("must provide quantity", 404)
        if not request.form.get("symbol"):
            return apology("must provide symbol", 404)
        try:
            shares = int(request.form.get("quantity"))
        except:
            return apology("only enter whole numbers for shares")
        if shares < 0:
            return apology("only buy positive numbers of shares")
        symbol = request.form.get("symbol")
        try:
            symbol = symbol.upper()
        except:
            return apology("only submit letters for stock symbols")
        try:
            lookedup = lookup(symbol)
            currentprice = float(lookedup['price'])
        except:
            return apology("no such symbol", 403)
        results = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        balance = round(results[0]["cash"], 2)
        total = currentprice * shares
        if balance >= total:
            #purchase confirmed
            date = datetime.datetime.now()
            # update amount of cash
            balance -= total
            print(balance)
            db.execute("UPDATE users SET cash = :balance WHERE id = :userid", balance=balance, userid=session["user_id"])
            check = db.execute("SELECT quantity FROM transactions WHERE userid=:userid AND symbol=:symbol",
                userid=session["user_id"], symbol=symbol)
            if len(check) == 1: # if you already own stock in this company
                newq = check[0]["quantity"] + shares
                db.execute("UPDATE transactions SET quantity = :newq WHERE userid=:userid AND symbol=:symbol",
                    newq=newq, userid=session["user_id"], symbol=symbol)
            else: # if you do not own stock in this company
                db.execute("INSERT INTO transactions VALUES (:userid, :symbol, :quantity, :price, :value, :date, :total)",
                    userid=session["user_id"], symbol=symbol, quantity=shares, price=currentprice, value=currentprice, date=date, total=usd(total))
            buy = True
            addhistory(buy, session["user_id"], symbol, shares, db)
            return redirect("/")
        else:
            apology("not enough funds", 403)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    rows = db.execute("SELECT * FROM history WHERE user = :user", user=session["user_id"])
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == 'POST':
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)
        symbol = request.form.get("symbol")
        symbol = symbol.upper()
        try:
            lookedup = lookup(symbol)
            quote = lookedup['price']
            quote = usd(quote)
            return render_template("quoted.html", symbol=symbol, quote=quote)
        except:
            return apology("no such symbol", 403)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == 'POST':
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        # Ensure username is unique
        if len(rows) == 1:
            return apology("Username unavailable", 403)
        else:
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"),
                hash=generate_password_hash(request.form.get("password")))
            return render_template("login.html")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == 'POST':
        if not request.form.get("quantity"):
            return apology("must provide quantity", 404)
        if not request.form.get("symbol"):
            return apology("must provide symbol", 404)
        try:
            shares = int(request.form.get("quantity"))
        except:
            return apology("only enter whole numbers for shares")
        if shares < 0:
            return apology("only sell positive numbers of shares")
        symbol = request.form.get("symbol")
        symbol = symbol.upper()
        try:
            lookedup = lookup(symbol)
            currentprice = float(lookedup['price'])
        except:
            return apology("no such symbol", 403)
        results = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        balance = round(results[0]["cash"], 2)
        total = currentprice * shares
        getshares = db.execute("SELECT quantity FROM transactions WHERE userid = :userid AND symbol = :symbol", userid=session["user_id"], symbol=symbol)
        currentshares = getshares[0]["quantity"]
        if shares > currentshares:
            return apology("you don't have that many shares", 403)
        else:
            buy = False
            balance += total
            db.execute("UPDATE users SET cash = :balance WHERE id = :userid", balance=balance, userid=session["user_id"])
            newq = currentshares - shares
            if newq == 0:
                db.execute("DELETE FROM transactions WHERE userid = :userid AND symbol = :symbol", userid=session["user_id"], symbol=symbol)
            else:
                db.execute("UPDATE transactions SET quantity = :newq WHERE userid = :userid AND symbol = :symbol", newq=newq, userid=session["user_id"], symbol=symbol)
            addhistory(buy, session["user_id"], symbol, shares, db)
            return redirect("/")
    else:
        return render_template("sell.html")


@app.route("/guillotine", methods=["GET"])
@login_required
def chop():
    db.execute("UPDATE users SET cash = 10000 WHERE id = :userid", userid=session["user_id"])
    return redirect("/")

@app.route("/clear", methods=["GET"])
@login_required
def clear():
    try:
        db.execute("DROP TABLE history")
    except:
        pass
    try:
        db.execute("CREATE TABLE history (date DATETIME, symbol TEXT, quantity NUMERIC, each NUMERIC, total NUMERIC, user NUMERIC)")
    except:
        pass
    return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)