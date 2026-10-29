#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=================================================="
echo " 🏝️ Dynamic Island - GitHub Yayınlama Yardımcısı"
echo "=================================================="
echo ""

# 1. Git kurulu mu kontrol et
if ! command -v git &> /dev/null; then
    echo "❌ Git bulunamadı!"
    echo "Lütfen önce terminale şu komutu girip Git'i kur:"
    echo "👉 sudo apt update && sudo apt install -y git"
    echo ""
    exit 1
fi

# 2. Git kullanıcı ayarları kontrolü
GIT_USER=$(git config --global user.name || true)
GIT_EMAIL=$(git config --global user.email || true)

if [ -z "$GIT_USER" ]; then
    read -p "👤 GitHub Adınız / Kullanıcı Adınız: " INPUT_USER
    git config --global user.name "$INPUT_USER"
fi

if [ -z "$GIT_EMAIL" ]; then
    read -p "📧 GitHub E-posta Adresiniz: " INPUT_EMAIL
    git config --global user.email "$INPUT_EMAIL"
fi

# 3. Git repo başlatma
if [ ! -d ".git" ]; then
    echo "📦 Git reposu başlatılıyor..."
    git init -b main
else
    echo "ℹ️ Mevcut Git reposu bulundu."
fi

# 4. Dosyaları ekle ve commit at
echo "📝 Dosyalar hazırlanıyor ve commit atılıyor..."
git add .
git commit -m "feat: initial release of Dynamic Island for Linux & Windows" || echo "Değişiklik yok ya da commit zaten hazır."

# 5. Uzak repo URL'si
echo ""
echo "🔗 GitHub'da oluşturduğun boş deponun (repository) URL'sini yapıştır."
echo "Örnek: https://github.com/eray/dynamic-island.git"
read -p "Repo URL: " REPO_URL

if [ -n "$REPO_URL" ]; then
    git remote remove origin 2>/dev/null || true
    git remote add origin "$REPO_URL"
    echo "🚀 GitHub'a yükleniyor (main dalı)..."
    git push -u origin main
    echo ""
    echo "🎉 Başarıyla GitHub'a yüklendi! Repon artık yayında!"
else
    echo "⚠️ URL girilmedi, push adımı atlandı."
    echo "Hazır olduğunda şunu çalıştırabilirsin:"
    echo "git remote add origin <REPO_URL> && git push -u origin main"
fi
