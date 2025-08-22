#load environment variables
if [ -f .devcontainer/.env ]; then
    export $(cat .devcontainer/.env | xargs)
fi  

#install python packages
sudo pip install -r Reviewer/requirements.txt --break-system-packages

sudo pip install --upgrade langchain-google-genai --break-system-packages
