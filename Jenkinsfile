pipeline {
    agent any

    triggers {
        cron('H 2 * * *')
    }

    parameters {
        string(name: 'APK_PATH', defaultValue: 'app-release.apk', description: 'APK path on Jenkins agent')
        string(name: 'DEVICE_SERIAL', defaultValue: '', description: 'Android device serial, optional when only one device is connected')
        string(name: 'MONKEY_EVENTS', defaultValue: '5000', description: 'Monkey event count')
        string(name: 'MONKEY_THROTTLE_MS', defaultValue: '200', description: 'Delay between Monkey events in ms')
        booleanParam(name: 'SEND_EMAIL_REPORT', defaultValue: false, description: 'Send pytest email report after run')
    }

    environment {
        MOBILE_APK_PATH = "${params.APK_PATH}"
        MOBILE_DEVICE_SERIAL = "${params.DEVICE_SERIAL}"
        MONKEY_EVENT_COUNT = "${params.MONKEY_EVENTS}"
        MONKEY_THROTTLE_MS = "${params.MONKEY_THROTTLE_MS}"
    }

    stages {
        stage('Install dependencies') {
            steps {
                bat 'python -m pip install -r requirements.txt'
            }
        }

        stage('Check adb device') {
            steps {
                bat 'adb devices -l'
            }
        }

        stage('Run Monkey') {
            steps {
                script {
                    def emailArg = params.SEND_EMAIL_REPORT ? '--email-report' : ''
                    bat "pytest tests/mobile/test_monkey.py -m monkey -s --junitxml=reports/junit/monkey.xml ${emailArg}"
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
            junit allowEmptyResults: true, testResults: 'reports/junit/*.xml'
        }
    }
}
