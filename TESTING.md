# Backend Testing Guide

This document describes how to test the backend manually with Postman, including the most important request flows, example payloads, and expected behavior.

> This guide reflects the current API surface implemented in this repository.

## 1. Prerequisites

- Python 3.11+
- MongoDB running locally on `mongodb://localhost:27017`
- Backend dependencies installed
- Postman installed

### Start the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at:

- Base URL: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

---

## 2. Postman setup

### Create a Postman environment

Create a new environment with these variables:

- `base_url`: `http://127.0.0.1:8000`
- `access_token`: empty
- `refresh_token`: empty
- `admin_email`: `admin@example.com`
- `admin_password`: `StrongPassword123`

### Recommended request headers

For authenticated requests, add:

- `Authorization: Bearer {{access_token}}`

For n8n-related testing, add:

- `X-API-KEY: insecure-n8n-secret-change-me`

---

## 3. Test flow: create the initial admin

This endpoint is intended for developer/bootstrap use.

### Request

- Method: `POST`
- URL: `{{base_url}}/users/initial-admin`
- Body: `raw JSON`

```json
{
  "name": "Developer Admin",
  "email": "admin@example.com",
  "password": "StrongPassword123"
}
```

### Expected result

- Status: `201 Created`
- Response body contains a created user with role `admin`

Example response shape:

```json
{
  "success": true,
  "message": "Initial admin created",
  "data": {
    "id": "...",
    "name": "Developer Admin",
    "email": "admin@example.com",
    "role": "admin",
    "status": "active"
  }
}
```

> If an admin already exists, the endpoint returns a conflict error.

---

## 4. Test flow: login, refresh, and logout

### 4.1 Login

- Method: `POST`
- URL: `{{base_url}}/auth/login`
- Body:

```json
{
  "email": "{{admin_email}}",
  "password": "{{admin_password}}"
}
```

### Expected result

- Status: `200 OK`
- Save the returned tokens into Postman variables:
  - `access_token`
  - `refresh_token`

Example response:

```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "accessToken": "...",
    "refreshToken": "...",
    "tokenType": "bearer"
  }
}
```

### 4.2 Refresh token

- Method: `POST`
- URL: `{{base_url}}/auth/refresh`
- Body:

```json
{
  "refreshToken": "{{refresh_token}}"
}
```

### Expected result

- Status: `200 OK`
- A fresh `accessToken` and `refreshToken` are returned

### 4.3 Logout

- Method: `POST`
- URL: `{{base_url}}/auth/logout`
- Body:

```json
{
  "refreshToken": "{{refresh_token}}"
}
```

### Expected result

- Status: `200 OK`
- The refresh token is invalidated for future use

---

## 5. Test flow: create a profile

Profiles are employee-scoped. Admins can act on behalf of a specific employee by passing `employeeId` as a query parameter.

### Request

- Method: `POST`
- URL: `{{base_url}}/profiles?employeeId=<employee_id>`
- Headers:
  - `Authorization: Bearer {{access_token}}`
- Body:

```json
{
  "name": "Primary Outreach",
  "gmailAccount": "demo.account@gmail.com",
  "dailyLimit": 100,
  "fromName": "Demo Team",
  "replyTo": "demo@example.com",
  "emailSubject": "Hello",
  "emailBody": "This is a sample email body",
  "filters": {
    "country": "US",
    "domain": "example.com"
  }
}
```

### Expected result

- Status: `200 OK`
- The new profile is returned in `data`

---

## 6. Test flow: list and fetch profiles

### List profiles

- Method: `GET`
- URL: `{{base_url}}/profiles`
- Header: `Authorization: Bearer {{access_token}}`

### Get one profile

- Method: `GET`
- URL: `{{base_url}}/profiles/<profile_id>`
- Header: `Authorization: Bearer {{access_token}}`

### Expected result

- Status: `200 OK`
- A list or a single profile object is returned in `data`

---

## 7. Test flow: activate/deactivate a profile

### Activate

- Method: `POST`
- URL: `{{base_url}}/profiles/<profile_id>/activate`
- Header: `Authorization: Bearer {{access_token}}`

### Deactivate

- Method: `POST`
- URL: `{{base_url}}/profiles/<profile_id>/deactivate`
- Header: `Authorization: Bearer {{access_token}}`

### Expected result

- Status: `200 OK`
- The profile object reflects the new active state

---

## 8. Test flow: upload leads via CSV or Excel

### Sample File content

Create a file named `leads.csv` or `leads.xlsx` with columns like:

```csv
fullName,email,company,website,country,state,city,domain,industry,designation,phone,linkedin,citation,mailSource
Jane Doe,jane@example.com,Example Corp,https://example.com,US,CA,Los Angeles,example.com,Software,Manager,1234567890,https://linkedin.com/in/jane,web,zoominfo
John Smith,john@example.com,Demo LLC,https://demo.com,US,NY,New York,demo.com,Marketing,Director,9876543210,https://linkedin.com/in/john,web,zoominfo
```

### Request in Postman

- Method: `POST`
- URL: `{{base_url}}/emails/upload`
- Headers:
  - `Authorization: Bearer {{access_token}}`
- Body: `form-data`
  - Key: `file`
  - Type: `File`
  - Value: select `leads.csv` or `leads.xlsx`
  - Key: `insertDuplicates`
  - Type: `Text`
  - Value: `false`

### Expected result

- Status: `200 OK`
- The response contains upload statistics and the processed records

---

## 9. Test flow: list uploaded emails and export CSV

### List emails

- Method: `GET`
- URL: `{{base_url}}/emails?includeDuplicates=true`
- Header: `Authorization: Bearer {{access_token}}`

### Export CSV

- Method: `GET`
- URL: `{{base_url}}/reports/emails/export`
- Header: `Authorization: Bearer {{access_token}}`

### Expected result

- Status: `200 OK`
- The export endpoint returns a CSV file as a download

---

## 10. Test flow: dashboard and logs

### Employee dashboard

- Method: `GET`
- URL: `{{base_url}}/dashboard/employee`
- Header: `Authorization: Bearer {{access_token}}`

### Admin dashboard

- Method: `GET`
- URL: `{{base_url}}/dashboard/admin`
- Header: `Authorization: Bearer {{access_token}}`

### Logs listing

- Method: `GET`
- URL: `{{base_url}}/logs`
- Header: `Authorization: Bearer {{access_token}}`

### Expected result

- Status: `200 OK`
- Dashboard and log data are returned in `data`

---

## 11. Optional: seed a sample employee for employee-scoped testing

If you want to test employee-only flows, you can seed an employee record with a temporary Python script.

```bash
cd backend
python -c "import asyncio
from app.employees.service import create_employee
from app.employees.schema import EmployeeCreate

async def main():
    payload = EmployeeCreate(
        name='Sample Employee',
        email='employee@example.com',
        password='StrongPassword123',
        employeeCode='EMP-001',
        department='Sales'
    )
    print(await create_employee(payload))

asyncio.run(main())"
```

Then use the employee account to log in and exercise employee-scoped endpoints.

---

## 12. Common checks

- Always verify the response envelope:

```json
{
  "success": true,
  "message": "...",
  "data": { }
}
```

- If a request fails due to auth, ensure the bearer token is present and not expired.
- If a request fails due to role restrictions, test with an admin token and then with an employee token.
- If MongoDB is not running, most endpoints will fail at startup or during data operations.

---

## 13. Quick Postman checklist

1. Start backend
2. Create initial admin
3. Login and save tokens
4. Create or seed a profile
5. Upload CSV leads
6. List emails and export CSV
7. Review dashboard and logs
