from fastapi.testclient import TestClient


def test_signup_success(client: TestClient):
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "newuser@example.com", "name": "New User", "password": "securepass123"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["user_id"] is not None
    assert "verify" in data["message"].lower()


def test_signup_duplicate_email(client: TestClient):
    user_data = {"email": "duplicate@example.com", "name": "User", "password": "password123"}

    response1 = client.post("/api/v1/auth/signup", json=user_data)
    assert response1.status_code == 201

    response2 = client.post("/api/v1/auth/signup", json=user_data)
    assert response2.status_code == 400
    assert "already registered" in response2.json()["detail"].lower()


def test_signup_invalid_email(client: TestClient):
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "invalid-email", "name": "User", "password": "password123"},
    )

    assert response.status_code == 422


def test_signup_short_password(client: TestClient):
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "name": "User", "password": "short"},
    )

    assert response.status_code == 422


def test_signin_success(client: TestClient):
    signup_data = {"email": "signin@example.com", "name": "Signin User", "password": "password123"}
    client.post("/api/v1/auth/signup", json=signup_data)

    response = client.post(
        "/api/v1/auth/signin", json={"email": "signin@example.com", "password": "password123"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] is not None
    assert data["token_type"] == "bearer"
    assert data["email"] == "signin@example.com"
    assert data["is_verified"] is False


def test_signin_wrong_password(client: TestClient):
    signup_data = {"email": "wrongpass@example.com", "name": "User", "password": "correctpassword"}
    client.post("/api/v1/auth/signup", json=signup_data)

    response = client.post(
        "/api/v1/auth/signin", json={"email": "wrongpass@example.com", "password": "wrongpassword"}
    )

    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_signin_nonexistent_user(client: TestClient):
    response = client.post(
        "/api/v1/auth/signin", json={"email": "nonexistent@example.com", "password": "password123"}
    )

    assert response.status_code == 401


async def test_verify_email_success(client: TestClient, db_session):
    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": "verify@example.com", "name": "Verify User", "password": "password123"},
    )
    assert signup_response.status_code == 201

    from app.repositories.otp_repository import OTPRepository
    from app.repositories.user_repository import UserRepository

    user_repo = UserRepository(db_session)
    otp_repo = OTPRepository(db_session)

    user = await user_repo.get_by_email("verify@example.com")
    latest_otp = await otp_repo.get_latest_otp(user.id)

    response = client.post(
        "/api/v1/auth/verify-email", json={"email": "verify@example.com", "otp": latest_otp.code}
    )

    assert response.status_code == 200
    data = response.json()
    assert "verified" in data["message"].lower()
    assert data["access_token"] is not None


def test_verify_email_invalid_otp(client: TestClient):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "invalidotp@example.com", "name": "User", "password": "password123"},
    )

    response = client.post(
        "/api/v1/auth/verify-email", json={"email": "invalidotp@example.com", "otp": "000000"}
    )

    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


def test_resend_otp_success(client: TestClient):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "resend@example.com", "name": "Resend User", "password": "password123"},
    )

    response = client.post("/api/v1/auth/resend-otp", json={"email": "resend@example.com"})

    assert response.status_code == 200
    data = response.json()
    assert "sent" in data["message"].lower()


def test_resend_otp_nonexistent_user(client: TestClient):
    response = client.post("/api/v1/auth/resend-otp", json={"email": "nonexistent@example.com"})

    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


async def test_complete_auth_flow(client: TestClient, db_session):
    email = "complete@example.com"

    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "name": "Complete User", "password": "password123"},
    )
    assert signup_response.status_code == 201

    from app.repositories.otp_repository import OTPRepository
    from app.repositories.user_repository import UserRepository

    user_repo = UserRepository(db_session)
    otp_repo = OTPRepository(db_session)

    user = await user_repo.get_by_email(email)
    latest_otp = await otp_repo.get_latest_otp(user.id)

    verify_response = client.post(
        "/api/v1/auth/verify-email", json={"email": email, "otp": latest_otp.code}
    )
    assert verify_response.status_code == 200

    signin_response = client.post(
        "/api/v1/auth/signin", json={"email": email, "password": "password123"}
    )
    assert signin_response.status_code == 200
    data = signin_response.json()
    assert data["is_verified"] is True
