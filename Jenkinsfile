pipeline {
    agent any

    environment {
        // Git
        GIT_CREDS  = 'github-token-emailapp'
        GIT_REPO   = 'https://github.com/sarammu7-bot/new-emailapp.git'
        GIT_BRANCH = 'main'

        // Deployment EC2
        SSH_KEY     = 'deploy-ec2-key'
        DEPLOY_USER = 'ubuntu'
        DEPLOY_HOST = '172.31.21.92'

        // ✅ Permanent production folder
        APP_DIR     = '/home/ubuntu/emailapp'
    }

    stages {

        stage('Checkout Code') {
            steps {
                git branch: "${GIT_BRANCH}",
                    credentialsId: "${GIT_CREDS}",
                    url: "${GIT_REPO}"
            }
        }

        stage('Build Frontend') {
            steps {
                sh '''
                if [ -d frontend ]; then
                    cd frontend
                    npm install
                    npm run build
                else
                    echo "⚠️ Frontend directory not found, skipping build"
                fi
                '''
            }
        }

        stage('Deploy & Migrate') {
    steps {
        sh """
        set -e

        echo "📦 Copying project to production folder"
        mkdir -p ${APP_DIR}
        rsync -av --delete ${WORKSPACE}/ ${APP_DIR}/ --exclude venv --exclude .git

        cd ${APP_DIR}

        echo "🧹 Rebuilding virtual environment"
        rm -rf venv
        python3 -m venv venv

        echo "⬆️ Installing dependencies"
        venv/bin/python -m pip install --upgrade pip
        venv/bin/python -m pip install -r requirements.txt

        echo "🗄 Running migrations"
        venv/bin/python manage.py migrate
        """
    }
}

stage('Restart Services') {
    steps {
        sh """
        sudo systemctl daemon-reload
        sudo systemctl restart fastapi
        sudo systemctl restart nginx
        """
    }
}

    post {
        success {
            echo '✅ stackly-email deployed successfully'
        }
        failure {
            echo '❌ Deployment failed – check stage logs'
        }
    }
}
