autoconf
autoreconf --force --install
sed -i '5587s/.*/'\'''\'')/' ./configure
sed -i '6486s/.*//' ./configure
./configure