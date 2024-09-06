import logging

from settings import db

log = logging.getLogger("main")


# pylint: disable=too-many-statements, too-many-locals
async def buy_this(user, server_id, item_name, amount):
    """
    Attempt to buy a specified quantity of an item from the in-game shop.

    This function allows a user to purchase a specified quantity of an item from
    the in-game shop. It checks the availability of the item, the user's balance,
    and updates the user's inventory accordingly.

    Parameters
    ----------
    user : discord.Member
        The Discord member making the purchase.
    server_id : int
        The ID of the server where the purchase is being made.
    item_name : str
        The name of the item to be purchased.
    amount : int
        The quantity of the item to be purchased.

    Returns
    -------
    list
        A list containing two elements:
        - A boolean value indicating whether the purchase was successful (True for success, False for failure).
        - An integer code indicating the result of the purchase operation (1 for item not found, 2 for insufficient balance, 3 for successful purchase, 4 for a database error).
    """
    sql_query = "SELECT * FROM `eve_shop` WHERE `shop` = 'shop'"
    mainshop = await db.select(sql_query, dictlist=True)

    name_ = None
    for item in mainshop:
        name = item["name"]
        if name == item_name:
            name_ = name
            price = item["price"]
            i_type = item["type"]
            break

    if name_ is None:
        return [False, 1]

    cost = price * amount

    user_id = user.id
    user_name = user.display_name

    # Get Bag data from User
    sql_query = f"SELECT * FROM `bag` WHERE `user_id` = {user_id} AND `guild_id` = {server_id} AND `item_name` = '{item_name}'"
    users = await db.select(sql_query, dictlist=True)

    sql = (
        f"SELECT * FROM `bank` WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
    )
    bal = await db.select(sql, single=True, dictlist=True)

    # Check if possible to buy
    if bal["wallet"] < cost:
        return [False, 3]

    sql_query = []

    try:
        if users:
            index = 0
            t = None
            for thing in users:
                n = thing["item_name"]
                if n == item_name:
                    old_amt = thing["item_quantity"]
                    new_amt = old_amt + amount
                    users[index]["item_quantity"] = new_amt
                    t = 1
                    break
                index += 1
            if t is None:
                obj = {"item_name": item_name, "item_quantity": amount, "type": i_type}
                users.append(obj)
            for item in users:
                item_name = item["item_name"]
                new_quantity = item["item_quantity"]
                i_type = item["type"]
            # Update Quantity
            sql_query.append(
                f"UPDATE `bag` SET `item_quantity` = {new_quantity} WHERE `user_id` = {user_id} AND `guild_id` = {server_id} AND `item_name` = '{item_name}'"
            )
        else:
            obj = {"item_name": item_name, "item_quantity": amount, "type": i_type}
            users = [obj]
            for item in users:
                item_name = item["item_name"]
                new_quantity = item["item_quantity"]
                i_type = item["type"]
            # Insert new Item
            sql_query.append(
                f"INSERT INTO `bag` (`user_id`, `user_name`, `guild_id`, `item_name`, `item_quantity`, `type`) VALUES ({user_id}, '{user_name}', {server_id}, '{item_name}', {new_quantity}, '{i_type}')"
            )
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Buy This] DB Error: {e}")
        return [False, 4]

    try:
        buy_balance = bal["wallet"] - cost
        sql_query.append(
            f"UPDATE bank SET `wallet` = {buy_balance} WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
        )
        sql_query = [query for query in sql_query if query is not None]
        await db.executemany_sql(sql_query)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Buy This] DB Error: {e}")
        return [False, 4]

    return [True, "Worked"]
