pipeline {
    agent any

    environment {
        // Git
        GIT_CREDS  = 'github-token-emailapp'
        GIT_REPO   = 'https://github.com/thestackly/stackly-email.git'
        GIT_BRANCH = 'main'

        // Deployment EC2
        SSH_KEY     = 'deploy-ec2-key'
        DEPLOY_USER = 'ubuntu'
        DEPLOY_HOST = '172.31.41.124'
        APP_DIR     = '/home/ubuntu/stackly-email'
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
                sshagent([env.SSH_KEY]) {
                    sh """
                    rsync -avz --delete \
                      --exclude='.git' \
                      --exclude='node_modules' \
                      --exclude='.ssh' \
                      frontend/dist \
                      django_backend \
                      email_project \
                      fastapi_app \
                      manage.py \
                      requirements.txt \
                      ${DEPLOY_USER}@${DEPLOY_HOST}:${APP_DIR}

                    ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} "
                        set -e
                        cd ${APP_DIR}

                        if [ ! -d venv ]; then
                            echo '🔧 Creating virtual environment'
                            python3 -m venv venv
                        fi

                        source venv/bin/activate
                        pip install --upgrade pip
                        pip install -r requirements.txt
                        python manage.py migrate
                    "
                    """
                }
            }
        }

        stage('Restart Services') {
            steps {
                sshagent([env.SSH_KEY]) {
                    sh """
                    ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} "
                        sudo systemctl restart fastapi
                        sudo systemctl restart nginx
                    "
                    """
                }
            }
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
