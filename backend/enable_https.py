"""
RoadWatch — Enable HTTPS for Camera & Accurate GPS
Run this INSTEAD of uvicorn to get full camera access.

Requirements: pip install uvicorn fastapi mkcert (or use the self-signed cert method below)
"""

import subprocess
import sys
import os

print("""
╔══════════════════════════════════════════════════════════╗
║         RoadWatch — HTTPS Setup for Live Camera          ║
╚══════════════════════════════════════════════════════════╝

Camera + accurate GPS require HTTPS (browser security policy).
This script generates a local SSL cert and starts the server.

Step 1: Install mkcert (one-time setup)
""")

# Method 1: mkcert (best, trusted cert)
print("OPTION A — Best (trusted, no browser warnings):")
print("  1. Download mkcert from: https://github.com/FiloSottile/mkcert/releases")
print("  2. Run: mkcert -install")
print("  3. Run: mkcert localhost 127.0.0.1")
print("  4. Then run this server:")
print()
print("  cd D:\\python\\road-damage-app\\backend")
print("  python enable_https.py --serve")
print()
print("OPTION B — Quick (self-signed, click 'Advanced > Proceed'):")
print("  python enable_https.py --self-signed")
print()

if '--serve' in sys.argv or '--self-signed' in sys.argv:
    import ssl
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    
    if '--self-signed' in sys.argv:
        # Generate self-signed cert
        print("Generating self-signed certificate...")
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from datetime import datetime, timedelta
            import ipaddress

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
            ])
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.utcnow())
                .not_valid_after(datetime.utcnow() + timedelta(days=365))
                .add_extension(
                    x509.SubjectAlternativeName([
                        x509.DNSName(u"localhost"),
                        x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')),
                    ]),
                    critical=False,
                )
                .sign(key, hashes.SHA256())
            )
            
            with open("cert.pem", "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            with open("key.pem", "wb") as f:
                f.write(key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption()
                ))
            
            cert_file, key_file = "cert.pem", "key.pem"
            print("✅ Self-signed cert generated!")
            
        except ImportError:
            print("Installing cryptography...")
            subprocess.run([sys.executable, "-m", "pip", "install", "cryptography", "--break-system-packages", "-q"])
            print("Run this script again.")
            sys.exit(0)
            
    else:
        # mkcert
        cert_file = "localhost+1.pem"
        key_file = "localhost+1-key.pem"
        if not os.path.exists(cert_file):
            print(f"ERROR: {cert_file} not found.")
            print("Run: mkcert localhost 127.0.0.1  first")
            sys.exit(1)
    
    os.chdir(os.path.join(backend_dir))
    
    print(f"\n🚀 Starting RoadWatch on https://localhost:8443")
    print("   Open: https://localhost:8443")
    print("   Camera will work! (Allow camera permission when asked)")
    print("\n   Press Ctrl+C to stop\n")
    
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8443",
        "--ssl-certfile", cert_file,
        "--ssl-keyfile", key_file,
        "--reload"
    ]
    subprocess.run(cmd)

else:
    print("━" * 60)
    print()
    print("QUICK START (HTTP — gallery only, no live camera):")
    print("  cd D:\\python\\road-damage-app\\backend")  
    print("  uvicorn app.main:app --reload")
    print("  → http://localhost:8000")
    print()
    print("FOR LIVE CAMERA (HTTPS required):")
    print("  Option 1 — Self-signed cert (easiest):")
    print("    pip install cryptography")
    print("    python enable_https.py --self-signed")
    print("    → https://localhost:8443")
    print()
    print("  Option 2 — Trusted cert (mkcert):")
    print("    Download mkcert.exe from GitHub releases")
    print("    mkcert -install")
    print("    mkcert localhost 127.0.0.1")
    print("    python enable_https.py --serve")
    print("    → https://localhost:8443")
    print()
    print("  Option 3 — ngrok (share with others):")
    print("    Download ngrok from https://ngrok.com")
    print("    Start uvicorn on port 8000 first")
    print("    ngrok http 8000")
    print("    → Use the https://xxxx.ngrok.io URL")
    print("    → Camera works on any device!")
    print()
    print("━" * 60)
    print("After HTTPS is running, open citizen portal:")
    print("  https://localhost:8443/citizen")
    print("  Camera button will open live viewfinder ✅")
    print("  GPS will be accurate (browser allows full accuracy on HTTPS) ✅")
