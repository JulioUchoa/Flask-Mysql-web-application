import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from datetime import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):

    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""


    # get from DB : user_id,  symbol, name, price, quantity, total_purc, date
    stocks_inf = db.execute("SELECT * FROM track WHERE id = ?", session["user_id"])


    for i in range(0, len(stocks_inf)):                                    # loop over the list of dicts
        lkup = lookup(stocks_inf[i]["symbol"])                             # get atualized stock values
        stocks_inf[i].update({"price": lkup["price"]})                     # update it in stocks_inf list
        total_atual = float(lkup["price"] * stocks_inf[i]["quantity"])     # update total_purchase values
        stocks_inf[i].update({"total_purc":total_atual})                   # update total_pur in stocks_inf list

    # current cash balance
    users_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    users_c = users_cash[0]["cash"]

    # format users_cash[0]["cash"] // it takes | 10000 | and returns | $ 10,000.00 |
    def cash(users_c):
        ch = f"${users_c:,.2f}"
        return ch

    # stocks total value (total_purc of every stock price owned together)
    total_o = db.execute("SELECT SUM(total_purc) FROM track WHERE id = ?", session["user_id"])

    total_owned = cash(0)

    if total_o[0]["SUM(total_purc)"] != None:
        total_owned = cash(total_o[0]["SUM(total_purc)"])


    return render_template("index.html", msg=stocks_inf, cash_avaliable=cash(users_c), total_owned=total_owned)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    # check if it was a POST request
    if request.method == "POST":

        # get symbol and shares from html plate
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")       # quantity of shares*

        # check if symbol is valid
        if not symbol or lookup(symbol) == None:
            return apology("Incorrect Input, please check it up and submit again.", 400)

        # check if user typed shares and if its valid
        elif not int(shares):
            return apology("Please, chose a positive number of shares.", 400)


        # get user cash suply
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        # get stock price and name from API
        stock_inf = lookup(symbol)
        stock_p = stock_inf['price']
        stock_n = stock_inf['name']

        # get total value from purchase
        total_purc = stock_p * int(shares)

        # check if user has enough money to afford the purchase
        if total_purc > user_cash[0]["cash"]:
            return apology("Sorry, you dont have enough money buying this sum of stocks", 403)

        # update users cash in DB
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ? ", total_purc, session["user_id"])

        # get date time
        td = datetime.now()
        data = td.strftime("%Y-%m-%d")

        # check if user has already this stock(SYMBOL)
        user_wallet = db.execute("SELECT symbol FROM track WHERE id = ?", session["user_id"])
        lt = []
        for i in range(0, len(user_wallet)):
            lt.append(user_wallet[i]["symbol"])        #lt = ["META", "AMZN", "TSLA", etc]

        # if wallet is empty or user doesnt have the stock we INSERT INTO track table the folowing parameters
        if lt == [] or symbol not in lt:

            # create database for tracking how bought what, at what price, its quantity, total purchase coast and date
            # CREATE TABLE track AS SELECT id FROM users;
            # ALTER TABLE track ADD symbol TEXT; ALTER TABLE ... ADD : name, price, quantity, total_purc, date
            db.execute("INSERT INTO track (id, symbol, name, price, quantity, total_purc, date) VALUES (?, ?, ?, ?, ?, ?, ?)", session["user_id"], symbol, stock_n, stock_p, int(shares), total_purc, data)

            #create database for tracking the history of buys and sells
            # CREATE TABLE history AS SELECT (id, symbol, name, price, quantity, total_purc, date) from track
            # ALTER TABLE history ADD COLUMN order_type in this case = BUY
            db.execute("INSERT INTO history (id, symbol, name, price, quantity, total_purc, date, order_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", session["user_id"], symbol, stock_n, stock_p, int(shares), total_purc, data, "BUY")


        # else we UPDATE what we already have >>
        else:
            db.execute("UPDATE track SET quantity = quantity + ?, total_purc = total_purc + ? WHERE symbol = ? AND id = ? ", int(shares), total_purc, symbol,  session["user_id"])
            db.execute("INSERT INTO history (id, symbol, name, price, quantity, total_purc, date, order_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", session["user_id"], symbol, stock_n, stock_p, int(shares), total_purc, data, "BUY")

        return redirect("/")

    return render_template("buy.html")


@app.route("/history", methods=["GET", "POST"])
@login_required
def history():
    """Show history of transactions"""
    if request.method == "GET":

        history = db.execute("SELECT * FROM history WHERE id = ?", session["user_id"])
        hist = history[0]

    return render_template("history.html", msg=history)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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

    # check if its a post requests
    if request.method == "POST":

        symbol = request.form.get("symbol")

        # check if symbol is valid
        if not symbol:
            return apology("Type a valid stock symbol", 400)

        message = lookup(symbol)

        # check if message is None >>
        if not message:
            return apology("You must provide a valid stock symbol", 400)


        return render_template("quoted.html", msg=message, usd_function=usd)


    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # save username, password for late SQL entry
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide username and password", 400)

        # Ensure username was not already taken
        users_db = db.execute("SELECT username FROM users")
        users = users_db[0]["username"]
        if username in users:
            return apology("Sorry, username already taken. chose another one.")

         # Ensure passoword and confimartion are the same
        elif confirmation != password:
            return apology("must retype password in confirmation area", 400)

        # Insert user / password into SQLITE
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, generate_password_hash(password, method='pbkdf2:sha1', salt_length=8))

        # saves users name on session
        session["name"] = username

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # check if its a POST request
    if request.method == "POST":

        # get symbols and shares from sell.html
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # create list with all stocks on users_id DB
        user_wallet = db.execute("SELECT symbol FROM track WHERE id = ?", session["user_id"])
        lt = []
        for i in range(0, len(user_wallet)):
            lt.append(user_wallet[i]["symbol"])        #lt = ["META", "AMZN", "TSLA", etc]


        # check if symbol is null and if its on DB
        if not symbol or symbol not in lt:
            return apology("Sorry, you should misstyped the stock symbol or you dont have it.", 400)

        # check if shares are not null and if its positive number
        elif not shares or int(shares) < 0:
            return apology("Please, chose a positive number of shares you want to sell", 400)

        # select number of stocks for chosen symbol
        quantity = db.execute("SELECT quantity FROM track WHERE symbol = ? AND id = ?", symbol, session["user_id"])
        qnt = quantity[0]["quantity"] # get [{"symbol":3}] guarda 3

        # check if shares is not greater then what user has in wallet (DB table track)
        if int(shares) > int(qnt):
            return apology("You dont have this much of stocks. First confirm the amount you got.", 400)


        # get atual stock price times stock number selled
        atual_p = lookup(symbol)
        atual_price = atual_p["price"]
        total_selled = atual_price * int(shares)


        # get stock price and name from API
        stock_inf = lookup(symbol)
        stock_p = stock_inf['price']
        stock_n = stock_inf['name']

        # get date time
        td = datetime.now()
        data = td.strftime("%Y-%m-%d")

        # add total selled value to DB (cash)-usersDB
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", total_selled, session["user_id"])

        # delete stock quantity and total_purc that was selled from DB(track)
        db.execute("UPDATE track SET quantity = quantity - ?, total_purc = total_purc - ? WHERE symbol = ? AND id = ?", int(shares), total_selled, symbol, session["user_id"])

        #create database for tracking the history of buys and sells
        # CREATE TABLE history AS SELECT (id, symbol, name, price, quantity, total_purc, date) from track
        # ALTER TABLE history ADD COLUMN order_type in this case = SELL
        db.execute("INSERT INTO history (id, symbol, name, price, quantity, total_purc, date, order_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", session["user_id"], symbol, stock_n, stock_p, int(shares), total_selled, data, "SELL")

        # check if shares (quantity) == 0: delete it from DB
        db.execute("DELETE FROM track WHERE quantity = 0 AND id = ?", session["user_id"])


        return redirect("/")


    user_wallet = db.execute("SELECT symbol FROM track WHERE id = ?", session["user_id"])
    lt = []
    for i in range(0, len(user_wallet)):
        lt.append(user_wallet[i]["symbol"])


    return render_template("sell.html", symbols_stack=lt)

#Defines route for changing password
@app.route("/changeP", methods=["GET", "POST"])
@login_required
def changeP():
    # get inputs from ChangePassword form
    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirmation = request.form.get("confirmation")

        # get  password hash from DB
        p = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
        pwhash = p[0]["hash"]

        # check if password matches with hash saved IN users
        if not check_password_hash(pwhash, old_password):
            return apology("hash não é igual")

        # check if confirmation matches new_password
        elif new_password != confirmation or not new_password or not confirmation:
            return apology("new password and confirmation dont match. check it and try again.")

        # generate new hash
        newhash = generate_password_hash(new_password, method='pbkdf2:sha1', salt_length=8)

        # update password_hash in DB-users
        db.execute("UPDATE users SET hash = ? WHERE id = ?", newhash, session["user_id"])



    return render_template("changeP.html")