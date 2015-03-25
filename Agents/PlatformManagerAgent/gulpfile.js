'use strict';

var browserify = require('browserify');
var buffer = require('gulp-buffer');
var del = require('del');
var gulp = require('gulp');
var inject = require('gulp-inject');
var rev = require('gulp-rev');
var source = require('vinyl-source-stream');

var BUILD_DIR = 'platformmanager/webroot/';
var APP_GLOB = '{css,js}/app-*';
var VENDOR_GLOB = '{css,js}/{normalize,vendor}-*';

gulp.task('default', ['watch']);
gulp.task('clean-app', cleanApp);
gulp.task('clean-vendor', cleanVendor);
gulp.task('css', ['clean-app'], css);
gulp.task('build', ['css', 'js', 'vendor'], htmlInject);
gulp.task('build-app', ['css', 'js'], htmlInject);
gulp.task('js', ['clean-app'], js);
gulp.task('watch', ['build'], watch);
gulp.task('vendor', ['clean-vendor'], vendor);

function cleanApp (callback) {
    del(BUILD_DIR + APP_GLOB, callback);
}

function cleanVendor(callback) {
    del(BUILD_DIR + VENDOR_GLOB, callback);
}

function css() {
    return gulp.src('ui-src/css/app.css')
        .pipe(rev())
        .pipe(gulp.dest(BUILD_DIR + 'css'));
}

function htmlInject() {
    return gulp.src('ui-src/index.html')
        .pipe(inject(gulp.src([VENDOR_GLOB, APP_GLOB], { cwd: BUILD_DIR}), { addRootSlash: false }))
        .pipe(gulp.dest(BUILD_DIR));
}

function js() {
    return browserify({
        bundleExternal: false,
        debug: true,
        entries: './ui-src/js/app',
        extensions: ['.jsx'],
    })
        .transform('reactify')
        .bundle()
        .pipe(source('app.js'))
        .pipe(buffer())
        .pipe(rev())
        .pipe(gulp.dest(BUILD_DIR + 'js'));
}

function vendor() {
    gulp.src('node_modules/normalize.css/normalize.css')
        .pipe(rev())
        .pipe(gulp.dest(BUILD_DIR + 'css'));

    return browserify({
        debug: true,
        noParse: [
            'bluebird/js/browser/bluebird.min.js',
            'events',
            'jquery/dist/jquery.min',
            'node-uuid',
            'react/dist/react.min'
        ],
    })
        .require([
            { file: 'bluebird/js/browser/bluebird.min.js', expose: 'bluebird' },
            'events',
            'flux',
            { file: 'jquery/dist/jquery.min', expose: 'jquery' },
            'node-uuid',
            { file: 'react/dist/react.min', expose: 'react' },
            'react/lib/keyMirror',
        ])
        .bundle()
        .pipe(source('vendor.js'))
        .pipe(buffer())
        .pipe(rev())
        .pipe(gulp.dest(BUILD_DIR + 'js'));
}

function watch() {
    return gulp.watch(['ui-src/**/*'], ['build-app']);
}
