from app.database.mongodb import get_database


async def create_indexes() -> None:
    db = get_database()

    await db["users"].create_index("email", unique=True)

    await db["employees"].create_index("userId", unique=True)
    await db["employees"].create_index("employeeCode", unique=True, sparse=True)

    await db["profiles"].create_index("employeeId")
    await db["profiles"].create_index([("employeeId", 1), ("profileName", 1)], unique=True)

    await db["emails"].create_index("email")
    await db["emails"].create_index("employeeId")
    await db["emails"].create_index("country")
    await db["emails"].create_index("domain")
    await db["emails"].create_index("industry")
    await db["emails"].create_index("uploadBatch")
    await db["emails"].create_index("createdAt")
    # Duplicate detection is scoped per employee, not globally.
    await db["emails"].create_index([("employeeId", 1), ("email", 1)])

    await db["logs"].create_index("employeeId")
    await db["logs"].create_index("profileId")
    await db["logs"].create_index("createdAt")
    await db["logs"].create_index("runDate")
